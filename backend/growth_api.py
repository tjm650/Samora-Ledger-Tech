"""Customer value, product growth and portfolio insight APIs."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from main import authorize_demo_read, authorize_staff, get_database

router = APIRouter(prefix="/api/v1/growth", tags=["Customer Growth Intelligence"])

def _rows(db, table, fields="*", page_size=1000):
    rows=[]; offset=0
    while True:
        order_key={"customers":"customer_id","customer_features":"customer_id","transactions":"transaction_id","customer_products":"customer_product_id","customer_value_scores":"value_score_id","product_recommendations":"recommendation_id"}.get(table,"created_at")
        page=(db.table(table).select(fields).order(order_key)
              .range(offset,offset+page_size-1).execute().data or [])
        rows.extend(page)
        if len(page)<page_size: return rows
        offset+=page_size

def _staff(x_api_key, authorization, write=False):
    # Growth Intelligence dashboard reads use the server-held API key only.
    # Staff authentication remains required for manual customer/product/outcome edits.
    if not write:
        authorize_demo_read(x_api_key, None)
        return None
    return authorize_staff(x_api_key, authorization, {"admin","analyst","relationship_manager"})

def _growth_demo_access(x_api_key):
    # Safe, aggregate/demo workflows are invoked through the Next.js server proxy.
    # The API key is never sent to or exposed in the browser.
    from main import authorize
    authorize(x_api_key)
    return None

@router.get("/overview")
def growth_overview(x_api_key:str|None=Header(default=None), authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization)
    db=get_database()
    customer_result=db.table("customers").select("customer_id",count="exact").execute()
    customer_total=customer_result.count or len(customer_result.data or [])
    today=date.today().isoformat()
    values=[]; offset=0
    while True:
        page=(db.table("customer_value_scores").select("value_band,value_score").eq("assessment_date",today)
              .order("value_score_id").range(offset,offset+999).execute().data or [])
        values.extend(page)
        if len(page)<1000: break
        offset+=1000
    recs=[]; offset=0
    while True:
        page=(db.table("product_recommendations").select("recommendation_id,recommendation_type,status,priority")
              .in_("status",["suggested","presented","accepted","converted"]).order("recommendation_id")
              .range(offset,offset+999).execute().data or [])
        recs.extend(page)
        if len(page)<1000: break
        offset+=1000
    insights=db.table("business_insights").select("*").eq("is_active",True).order("generated_at",desc=True).limit(12).execute().data or []
    return {"customers_total":customer_total,"customers_scored":len(values),
      "value_distribution":{band:sum(1 for v in values if v["value_band"]==band) for band in ["emerging","core","high_value","top_value"]},
      "recommendations_total":len(recs),"cross_sell_count":sum(1 for r in recs if r["recommendation_type"]=="cross_sell"),
      "up_sell_count":sum(1 for r in recs if r["recommendation_type"]=="up_sell"),
      "high_priority_count":sum(1 for r in recs if r["priority"]=="high"),"insights":insights}

@router.get("/customers/value")
def customer_value(page:int=1,page_size:int=25,band:str|None=None,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization)
    db=get_database(); today=date.today().isoformat()
    query=db.table("customer_value_scores").select("*",count="exact").eq("assessment_date",today)
    if band: query=query.eq("value_band",band)
    result=query.order("value_score",desc=True).range((page-1)*min(page_size,100),page*min(page_size,100)-1).execute()
    scores=result.data or []; ids=[s["customer_id"] for s in scores]
    customers=db.table("customers").select("customer_id,full_name,email,account_tier,created_at").in_("customer_id",ids).execute().data or [] if ids else []
    lookup={c["customer_id"]:c for c in customers}
    return {"customers":[{**lookup.get(s["customer_id"],{}),**s} for s in scores],"total":result.count or len(scores),"page":page,"page_size":min(page_size,100)}

@router.get("/recommendations")
def recommendations(status:str|None=None,kind:Literal["cross_sell","up_sell"]|None=None,page:int=1,page_size:int=50,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization)
    db=get_database(); q=db.table("product_recommendations").select("*",count="exact").order("propensity_score",desc=True)
    if status:q=q.eq("status",status)
    if kind:q=q.eq("recommendation_type",kind)
    result=q.range((page-1)*min(page_size,100),page*min(page_size,100)-1).execute()
    rows=result.data or []; cids=list({r["customer_id"] for r in rows}); pids=list({r["product_id"] for r in rows})
    customers=db.table("customers").select("customer_id,full_name,email,account_tier").in_("customer_id",cids).execute().data or [] if cids else []
    products=db.table("banking_products").select("product_id,product_name,product_category,product_tier").in_("product_id",pids).execute().data or [] if pids else []
    cm={x["customer_id"]:x for x in customers}; pm={x["product_id"]:x for x in products}
    return {"recommendations":[{**r,"customer":cm.get(r["customer_id"],{}),"product":pm.get(r["product_id"],{})} for r in rows],"total":result.count or len(rows)}

class ProductInput(BaseModel):
    product_code:str=Field(min_length=2,max_length=60)
    product_name:str=Field(min_length=2,max_length=120)
    product_category:str=Field(min_length=2,max_length=80)
    product_tier:str|None=None
    description:str|None=None
    eligibility_notes:str|None=None

@router.post("/products")
def create_product(payload:ProductInput,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,True)
    result=get_database().table("banking_products").insert(payload.model_dump()).execute().data or []
    if not result: raise HTTPException(500,"Product was not saved")
    return {"product":result[0]}

class OwnershipInput(BaseModel):
    product_id:str
    status:Literal["active","inactive","closed","pending"]="active"
    opened_at:date|None=None
    notes:str|None=None

@router.post("/customers/{customer_id}/products")
def assign_product(customer_id:str,payload:OwnershipInput,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,True)
    db=get_database()
    if not (db.table("customers").select("customer_id").eq("customer_id",customer_id).maybe_single().execute().data):
        raise HTTPException(404,"Customer not found")
    row={"customer_id":customer_id,**payload.model_dump(mode="json")}
    result=db.table("customer_products").upsert(row,on_conflict="customer_id,product_id").execute().data or []
    return {"customer_product":result[0] if result else row}

class OutcomeInput(BaseModel):
    outcome:Literal["presented","accepted","declined","converted","no_response"]
    outcome_notes:str|None=None

@router.post("/recommendations/{recommendation_id}/outcomes")
def record_outcome(recommendation_id:str,payload:OutcomeInput,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    actor=_staff(x_api_key,authorization,True)
    db=get_database()
    rec=db.table("product_recommendations").select("recommendation_id").eq("recommendation_id",recommendation_id).maybe_single().execute().data
    if not rec: raise HTTPException(404,"Recommendation not found")
    user_id=str(actor.id) if actor else None
    db.table("recommendation_outcomes").insert({"recommendation_id":recommendation_id,"outcome":payload.outcome,"recorded_by":user_id,"outcome_notes":payload.outcome_notes}).execute()
    db.table("product_recommendations").update({"status":payload.outcome,"updated_at":datetime.now(timezone.utc).isoformat()}).eq("recommendation_id",recommendation_id).execute()
    return {"recorded":True,"status":payload.outcome}

@router.post("/run")
def run_growth_intelligence(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _growth_demo_access(x_api_key)
    db=get_database(); today=date.today().isoformat(); cutoff=(datetime.now(timezone.utc)-timedelta(days=90)).isoformat()
    customers=_rows(db,"customers","customer_id,account_tier,created_at,full_name")
    if not customers:return {"customers_processed":0,"value_scores_written":0,"recommendations_written":0,"insights_written":0,"message":"No customer records are available. Import approved BancABC data before running growth intelligence."}
    features=_rows(db,"customer_features","customer_id,balance_avg_30d,frequency_30d,monetary_spend_90d,behavior_segment")
    transactions=[]; offset=0; page_size=1000
    while True:
        page=(db.table("transactions").select("transaction_id,customer_id,amount,transaction_type,merchant_category")
              .gte("timestamp",cutoff).order("transaction_id").range(offset,offset+page_size-1).execute().data or [])
        transactions.extend(page)
        if len(page)<page_size: break
        offset+=page_size
    products=db.table("banking_products").select("*").eq("is_active",True).execute().data or []
    owned=_rows(db,"customer_products","customer_id,product_id,status")
    owned=[x for x in owned if x.get("status")=="active"]
    fm={x["customer_id"]:x for x in features}; owned_map=defaultdict(set)
    for x in owned:owned_map[x["customer_id"]].add(x["product_id"])
    activity=defaultdict(lambda:{"count":0,"debit":0.0,"credit":0.0,"travel":0.0,"transfers":0,"salary":0.0})
    for t in transactions:
        a=activity[t["customer_id"]]; amount=float(t.get("amount") or 0); a["count"]+=1
        if t.get("transaction_type")=="Debit":
            a["debit"]+=amount
            if t.get("merchant_category")=="Travel":a["travel"]+=amount
            if t.get("merchant_category")=="Transfers":a["transfers"]+=1
        else:
            a["credit"]+=amount
            if t.get("merchant_category")=="Salary":a["salary"]+=amount
    metrics=[]
    for c in customers:
        cid=c["customer_id"]; f=fm.get(cid,{}); a=activity[cid]
        created=datetime.fromisoformat(str(c["created_at"]).replace("Z","+00:00")) if c.get("created_at") else datetime.now(timezone.utc)
        age=max(0,(datetime.now(timezone.utc)-created.replace(tzinfo=created.tzinfo or timezone.utc)).days)
        metrics.append({"customer":c,"features":f,"activity":a,"age":age,"balance":float(f.get("balance_avg_30d") or 0),"spend":float(f.get("monetary_spend_90d") or a["debit"]),"frequency":int(f.get("frequency_30d") or a["count"])})
    max_spend=max([m["spend"] for m in metrics] or [1]) or 1; max_balance=max([m["balance"] for m in metrics] or [1]) or 1
    max_freq=max([m["frequency"] for m in metrics] or [1]) or 1; max_age=max([m["age"] for m in metrics] or [1]) or 1
    score_rows=[]; rec_rows=[]
    existing_recs=_rows(db,"product_recommendations","customer_id,product_id,recommendation_type,status")
    existing_status={(x["customer_id"],x["product_id"],x["recommendation_type"]):x["status"] for x in existing_recs}
    product_by_code={p["product_code"]:p for p in products}
    for m in metrics:
        c=m["customer"]; cid=c["customer_id"]; a=m["activity"]
        spend_n=m["spend"]/max_spend; balance_n=m["balance"]/max_balance; freq_n=m["frequency"]/max_freq; age_n=m["age"]/max_age
        score=round(100*(.40*spend_n+.35*balance_n+.15*freq_n+.10*age_n),2)
        band="top_value" if score>=80 else ("high_value" if score>=60 else ("core" if score>=30 else "emerging"))
        score_rows.append({"customer_id":cid,"assessment_date":today,"value_score":score,"value_band":band,"transaction_value_90d":round(m["spend"],2),"transaction_count_90d":a["count"],"average_balance_30d":round(m["balance"],2),"relationship_age_days":m["age"],"profitability_status":"not_available","score_components":{"spend_normalised":round(spend_n,4),"balance_normalised":round(balance_n,4),"frequency_normalised":round(freq_n,4),"tenure_normalised":round(age_n,4),"method":"relative portfolio score; not measured profitability"}})
        candidates=[]
        def add(code,kind,score_value,reason,evidence):
            p=product_by_code.get(code)
            key=(cid,p["product_id"],kind) if p else None
            previous_status=existing_status.get(key) if key else None
            if p and p["product_id"] not in owned_map[cid] and previous_status not in {"accepted","declined","converted","dismissed"}:
                candidates.append({"customer_id":cid,"product_id":p["product_id"],"recommendation_type":kind,"propensity_score":round(min(99,max(1,score_value)),2),"priority":"high" if score_value>=75 else ("medium" if score_value>=45 else "low"),"rationale":reason,"evidence":evidence,"status":previous_status or "suggested","generated_at":datetime.now(timezone.utc).isoformat()})
        if m["balance"]>=2500 or a["salary"]>0:add("SAVINGS_PLUS","cross_sell",45+min(35,m["balance"]/500),"Regular inflows or maintained balances suggest a savings conversation may be relevant.",{"average_balance_30d":m["balance"],"salary_credits_90d":a["salary"]})
        if m["balance"]>=5000 and c.get("account_tier")!="Platinum":add("PREMIUM_BANKING","up_sell" if c.get("account_tier") in {"Standard","Gold"} else "cross_sell",55+min(35,m["balance"]/1000),"Sustained average balance may justify a review of premium banking benefits and fees.",{"average_balance_30d":m["balance"],"current_tier":c.get("account_tier")})
        if m["balance"]>=8000:add("INVESTMENT_SERVICES","cross_sell",50+min(40,m["balance"]/1000),"Balance profile may support a suitability-led investment discussion; risk appetite must be assessed.",{"average_balance_30d":m["balance"]})
        if a["debit"]>0 and a["travel"]/a["debit"]>=.20:add("INTERNATIONAL_BANKING","cross_sell",50+min(35,100*a["travel"]/a["debit"]),"Travel-related debit activity indicates a possible need for international banking services.",{"travel_debit_share":round(a["travel"]/a["debit"],3)})
        if a["transfers"]>=12:add("BUSINESS_BANKING","cross_sell",45+min(35,a["transfers"]),"Repeated transfer activity may warrant a conversation about business banking needs.",{"transfer_count_90d":a["transfers"]})
        rec_rows.extend(sorted(candidates,key=lambda x:x["propensity_score"],reverse=True)[:2])
    for start in range(0,len(score_rows),250):db.table("customer_value_scores").upsert(score_rows[start:start+250],on_conflict="customer_id,assessment_date").execute()
    for start in range(0,len(rec_rows),250):db.table("product_recommendations").upsert(rec_rows[start:start+250],on_conflict="customer_id,product_id,recommendation_type").execute()
    bands=defaultdict(int)
    for s in score_rows:bands[s["value_band"]]+=1
    insight_rows=[
      {"insight_key":"portfolio_value_distribution","insight_type":"customer_value","title":"Customer value distribution","summary":f"{bands['high_value']+bands['top_value']} of {len(score_rows)} customers are in the high or top relative value bands.","recommended_action":"Prioritise relationship reviews for high-value customers and investigate emerging customers with strong growth signals.","severity":"attention" if bands["high_value"]+bands["top_value"] else "info","metric_value":bands["high_value"]+bands["top_value"],"metric_unit":"customers","evidence":{"bands":dict(bands),"scoring_method":"relative portfolio score; profitability not measured"},"generated_by":"growth-rules-v1"},
      {"insight_key":"product_opportunity_pipeline","insight_type":"product_growth","title":"Product opportunity pipeline","summary":f"{len(rec_rows)} product recommendations were generated from observed transaction and balance patterns.","recommended_action":"Have relationship managers validate customer needs, suitability, fees and eligibility before presenting offers.","severity":"info","metric_value":len(rec_rows),"metric_unit":"recommendations","evidence":{"cross_sell":sum(1 for r in rec_rows if r["recommendation_type"]=="cross_sell"),"up_sell":sum(1 for r in rec_rows if r["recommendation_type"]=="up_sell")},"generated_by":"growth-rules-v1"}
    ]
    db.table("business_insights").upsert(insight_rows,on_conflict="insight_key,generated_by").execute()
    return {"customers_processed":len(customers),"value_scores_written":len(score_rows),"recommendations_written":len(rec_rows),"insights_written":len(insight_rows),"value_distribution":dict(bands),"profitability_measured":False,"method":"transparent relative scoring and rules-based product propensity; not a trained ML model"}

class AssistantQuestion(BaseModel):
    question:str=Field(min_length=8,max_length=1200)

@router.post("/assistant")
def business_intelligence_assistant(payload:AssistantQuestion,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _growth_demo_access(x_api_key)
    import json, os, urllib.error, urllib.request
    api_key=os.getenv("OPENAI_API_KEY")
    if not api_key: raise HTTPException(503,"AI assistant is not configured. Add OPENAI_API_KEY to the Render service environment.")
    db=get_database()
    customers=db.table("customers").select("customer_id",count="exact").execute()
    values=db.table("customer_value_scores").select("value_band,value_score").eq("assessment_date",date.today().isoformat()).execute().data or []
    risks=db.table("predictive_insights").select("churn_risk_score,primary_churn_driver").execute().data or []
    recs=db.table("product_recommendations").select("recommendation_type,status,priority").in_("status",["suggested","presented","accepted","converted"]).execute().data or []
    insights=db.table("business_insights").select("title,summary,recommended_action").eq("is_active",True).limit(20).execute().data or []
    context={"customer_count":customers.count or 0,"value_band_counts":{b:sum(1 for v in values if v["value_band"]==b) for b in ["emerging","core","high_value","top_value"]},"rules_based_churn_risk":{"assessed":len(risks),"high":sum(1 for x in risks if float(x["churn_risk_score"])>=60),"top_drivers":dict(__import__("collections").Counter(x.get("primary_churn_driver") or "Unclassified" for x in risks).most_common(5))},"product_opportunities":{"total":len(recs),"cross_sell":sum(1 for x in recs if x["recommendation_type"]=="cross_sell"),"up_sell":sum(1 for x in recs if x["recommendation_type"]=="up_sell"),"high_priority":sum(1 for x in recs if x["priority"]=="high")},"latest_insights":insights}
    model=os.getenv("OPENAI_MODEL","gpt-4o-mini")
    body={"model":model,"temperature":0.2,"messages":[{"role":"system","content":"You are Samora Ledger Tech's banking business intelligence assistant. Answer only from the supplied aggregate portfolio context. Never invent metrics, customer facts, product terms, eligibility or profitability. Clearly distinguish observed facts from hypotheses. Churn scores are rules-based indicators, not validated probabilities. Customer value is relative, not bank profitability. Product recommendations require human suitability, consent and eligibility checks. If the context does not contain enough information, say so and identify the missing data. Give concise, actionable executive analysis."},{"role":"user","content":"Portfolio context (aggregate only): "+json.dumps(context)+"\n\nQuestion: "+payload.question}]}
    request=urllib.request.Request("https://api.openai.com/v1/chat/completions",data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(request,timeout=35) as response: result=json.loads(response.read().decode())
        answer=result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        detail=exc.read().decode(errors="ignore")[:500]
        raise HTTPException(502,"AI provider request failed: "+detail) from exc
    except Exception as exc:
        raise HTTPException(502,"Unable to generate an AI business insight") from exc
    return {"answer":answer,"model":model,"context_scope":"aggregate portfolio data only","generated_at":datetime.now(timezone.utc).isoformat()}

@router.get("/products")
def list_products(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization)
    rows=get_database().table("banking_products").select("*").eq("is_active",True).order("product_category").execute().data or []
    return {"products":rows}

@router.get("/customers/{customer_id}/products")
def customer_products(customer_id:str,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization)
    db=get_database()
    owned=db.table("customer_products").select("*").eq("customer_id",customer_id).order("created_at",desc=True).execute().data or []
    ids=[x["product_id"] for x in owned]
    products=db.table("banking_products").select("product_id,product_name,product_category,product_tier").in_("product_id",ids).execute().data or [] if ids else []
    lookup={p["product_id"]:p for p in products}
    return {"products":[{**x,"product":lookup.get(x["product_id"],{})} for x in owned]}

class ChurnOutcomeInput(BaseModel):
    outcome_date:date
    outcome:Literal["churned","retained","reactivated","unknown"]
    evidence_source:str|None=None
    notes:str|None=None

@router.post("/customers/{customer_id}/churn-outcomes")
def record_churn_outcome(customer_id:str,payload:ChurnOutcomeInput,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    actor=_staff(x_api_key,authorization,True)
    db=get_database()
    row={"customer_id":customer_id,**payload.model_dump(mode="json"),"recorded_by":str(actor.id) if actor else None}
    try:
        saved=db.table("customer_churn_outcomes").upsert(row,on_conflict="customer_id,outcome_date").execute().data or []
    except Exception as exc:
        raise HTTPException(400,"Unable to save the verified churn outcome") from exc
    return {"outcome":saved[0] if saved else row}
