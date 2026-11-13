from __future__ import annotations
import logging, os, secrets, time
from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from analytics import run_pipeline, explain_customer
from data_seeder import seed as seed_demo_data
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
log=logging.getLogger("samora")
app=FastAPI(title="Samora Ledger Tech API",version="1.1.0")
_OVERVIEW_CACHE:dict[int,tuple[float,dict]]={}
_OVERVIEW_CACHE_TTL_SECONDS=30
origins=[x.strip() for x in os.getenv("API_CORS_ORIGINS","http://localhost:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["GET","POST","PATCH"],allow_headers=["Authorization","Content-Type","X-API-Key"])

def authorize(x_api_key: str|None):
    expected=os.getenv("API_KEY")
    if not expected: raise HTTPException(503,"API_KEY is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key,expected): raise HTTPException(401,"Invalid API key")

def authorize_staff(x_api_key: str|None, authorization: str|None, allowed_roles=None):
    authorize(x_api_key)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401,"Staff sign-in required")
    token=authorization.split(" ",1)[1].strip()
    if not token: raise HTTPException(401,"Staff sign-in required")
    try:
        user=get_database().auth.get_user(token).user
    except Exception as exc:
        raise HTTPException(401,"Staff session is invalid or expired") from exc
    if not user: raise HTTPException(401,"Staff session is invalid or expired")
    role=(getattr(user,"app_metadata",None) or {}).get("role")
    allowed=allowed_roles or {"admin","analyst","relationship_manager","executive"}
    if role not in allowed: raise HTTPException(403,"Your staff role is not authorised")
    return user

def get_database():
    from supabase import create_client
    url=os.getenv("SUPABASE_URL"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key: raise HTTPException(503,"Database connection is not configured")
    return create_client(url,key)

def fetch_all_insights(db):
    rows=[]; offset=0; page_size=1000
    while True:
        page=(db.table("predictive_insights")
            .select("churn_risk_score,primary_churn_driver,evaluated_at")
            .order("customer_id")
            .range(offset,offset+page_size-1).execute().data or [])
        rows.extend(page)
        if len(page)<page_size: break
        offset+=page_size
    return rows

def parse_timestamp(value):
    if isinstance(value,datetime): return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"))
    return stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)

def fetch_transactions_since(db, cutoff):
    rows=[]; offset=0; page_size=1000
    while True:
        page=(db.table("transactions")
            .select("transaction_id,timestamp,amount,transaction_type,merchant_category,channel,post_transaction_balance")
            .gte("timestamp",cutoff.isoformat())
            .order("timestamp",desc=True)
            .range(offset,offset+page_size-1).execute().data or [])
        rows.extend(page)
        if len(page)<page_size: break
        offset+=page_size
    return rows

def build_executive_overview(transactions, insights, now, period_days):
    current_cutoff=now-timedelta(days=30); prior_cutoff=now-timedelta(days=60)
    daily=defaultdict(lambda:{"debits":0.0,"credits":0.0,"count":0})
    categories=defaultdict(lambda:{"count":0,"volume":0.0})
    channels=defaultdict(lambda:{"count":0,"volume":0.0})
    current={"count":0,"debits":0.0,"credits":0.0,"amount":0.0}
    previous={"count":0,"debits":0.0,"credits":0.0}
    for row in transactions:
        stamp=parse_timestamp(row["timestamp"]); amount=float(row["amount"]); kind=row["transaction_type"]
        category=row.get("merchant_category") or "Uncategorised"; channel=row.get("channel") or "Unknown"
        if stamp>=current_cutoff:
            current["count"]+=1; current["amount"]+=amount
            if kind=="Debit": current["debits"]+=amount
            else: current["credits"]+=amount
            key=stamp.date().isoformat(); daily[key]["count"]+=1
            daily[key]["debits" if kind=="Debit" else "credits"]+=amount
        elif stamp>=prior_cutoff:
            previous["count"]+=1
            previous["debits" if kind=="Debit" else "credits"]+=amount
        categories[category]["count"]+=1; categories[category]["volume"]+=amount
        channels[channel]["count"]+=1; channels[channel]["volume"]+=amount
    trend=[]
    for step in range(29,-1,-1):
        day=(now-timedelta(days=step)).date().isoformat(); value=daily[day]
        trend.append({"date":day,"transactions":value["count"],"debit_volume":round(value["debits"],2),"credit_volume":round(value["credits"],2)})
    scores=[float(x["churn_risk_score"]) for x in insights]
    risk={"low":sum(1 for x in scores if x<30),"moderate":sum(1 for x in scores if 30<=x<60),"high":sum(1 for x in scores if x>=60)}
    drivers=Counter((x.get("primary_churn_driver") or "Not classified") for x in insights)
    latest=max((x.get("evaluated_at") for x in insights if x.get("evaluated_at")),default=None)
    def pct_change(new,old):
        if old==0: return None
        return round(((new-old)/old)*100,1)
    return {
      "generated_at":now.isoformat(),"period_days":period_days,
      "metrics":{
        "transactions_30d":current["count"],"debit_volume_30d":round(current["debits"],2),
        "credit_volume_30d":round(current["credits"],2),"net_flow_30d":round(current["credits"]-current["debits"],2),
        "average_transaction_30d":round(current["amount"]/current["count"],2) if current["count"] else 0,
        "transactions_change_pct":pct_change(current["count"],previous["count"]),
        "debit_volume_change_pct":pct_change(current["debits"],previous["debits"]),
        "credit_volume_change_pct":pct_change(current["credits"],previous["credits"]),
        "evaluated_relationships":len(scores),"average_risk_score":round(sum(scores)/len(scores),1) if scores else 0,
        "high_risk_relationships":risk["high"],"high_risk_share_pct":round(risk["high"]*100/len(scores),1) if scores else 0
      },
      "risk_distribution":[{"name":"Low","count":risk["low"]},{"name":"Moderate","count":risk["moderate"]},{"name":"High","count":risk["high"]}],
      "risk_drivers":[{"name":name,"count":count} for name,count in drivers.most_common(8)],
      "transaction_trend":trend,
      "category_breakdown":[{"name":name,"count":v["count"],"volume":round(v["volume"],2)} for name,v in sorted(categories.items(),key=lambda item:item[1]["volume"],reverse=True)],
      "channel_breakdown":[{"name":name,"count":v["count"],"volume":round(v["volume"],2)} for name,v in sorted(channels.items(),key=lambda item:item[1]["count"],reverse=True)],
      "last_pipeline_run":latest
    }

@app.get("/health")
def health():
    return {"status":"ok","service":"samora-ledger-tech"}

@app.post("/api/v1/run-pipeline")
def pipeline(x_api_key: str|None=Header(default=None)):
    authorize(x_api_key)
    try:
        result=run_pipeline(); _OVERVIEW_CACHE.clear()
        return {"status":"completed",**result}
    except Exception as exc:
        log.exception("Analytics pipeline failed")
        raise HTTPException(500,"Pipeline failed; inspect service logs") from exc

@app.get("/api/v1/executive/overview")
def executive_overview(period_days:int=Query(default=90,ge=30,le=365),x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    authorize_staff(x_api_key,authorization,{"admin","analyst","executive","relationship_manager"})
    try:
        cached=_OVERVIEW_CACHE.get(period_days)
        if cached and time.monotonic()-cached[0]<_OVERVIEW_CACHE_TTL_SECONDS: return cached[1]
        now=datetime.now(timezone.utc); db=get_database()
        transactions=fetch_transactions_since(db,now-timedelta(days=period_days))
        insights=fetch_all_insights(db)
        result=build_executive_overview(transactions,insights,now,period_days)
        _OVERVIEW_CACHE[period_days]=(time.monotonic(),result)
        return result
    except HTTPException: raise
    except Exception as exc:
        log.exception("Executive overview retrieval failed")
        raise HTTPException(500,"Unable to retrieve executive analytics") from exc

@app.get("/api/v1/executive/transactions")
def executive_transactions(
    limit:int=Query(default=50,ge=1,le=100),offset:int=Query(default=0,ge=0),
    transaction_type:str|None=Query(default=None),category:str|None=Query(default=None),
    x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)
):
    authorize_staff(x_api_key,authorization,{"admin","analyst","executive","relationship_manager"})
    allowed_types={"Debit","Credit"}
    allowed_categories={"Groceries","Travel","Luxury","Utilities","Salary","ATM","Transfers"}
    if transaction_type and transaction_type not in allowed_types: raise HTTPException(422,"Unsupported transaction type")
    if category and category not in allowed_categories: raise HTTPException(422,"Unsupported transaction category")
    try:
        db=get_database()
        query=db.table("transactions").select("transaction_id,timestamp,amount,transaction_type,merchant_category,channel,post_transaction_balance",count="exact")
        if transaction_type: query=query.eq("transaction_type",transaction_type)
        if category: query=query.eq("merchant_category",category)
        result=query.order("timestamp",desc=True).range(offset,offset+limit-1).execute()
        rows=[{**row,"reference":str(row["transaction_id"])[:8].upper()} for row in (result.data or [])]
        return {"transactions":rows,"total":result.count or 0,"limit":limit,"offset":offset}
    except HTTPException: raise
    except Exception as exc:
        log.exception("Executive transaction retrieval failed")
        raise HTTPException(500,"Unable to retrieve transaction activity") from exc

@app.post("/api/v1/admin/seed-and-run-demo")
def seed_and_run_demo(x_api_key: str|None=Header(default=None)):
    authorize(x_api_key)
    if os.getenv("ALLOW_DEMO_SEEDING") != "true":
        raise HTTPException(403,"Demo seeding is disabled; enable ALLOW_DEMO_SEEDING only for a disposable demo database")
    try:
        db=get_database()
        existing=db.table("customers").select("customer_id",count="exact").limit(1).execute()
        if (existing.count or 0)>0: raise HTTPException(409,"Demo seeding is one-shot and this database is not empty")
        seed_result=seed_demo_data(); pipeline_result=run_pipeline()
        return {"status":"completed","seed":seed_result,"pipeline":pipeline_result}
    except HTTPException: raise
    except Exception as exc:
        log.exception("Demo seed and analytics run failed")
        raise HTTPException(500,"Demo seed or analytics run failed; inspect service logs") from exc

# Internal compatibility endpoints retained for existing integrations; the executive
# web application intentionally does not expose customer portfolio or individual profiles.
@app.get("/api/v1/customers")
def list_customers(x_api_key: str|None=Header(default=None),authorization:str|None=Header(default=None)):
    authorize_staff(x_api_key,authorization)
    try:
        db=get_database()
        customers=(db.table("customers").select("customer_id,full_name,email,account_tier,created_at").order("full_name").range(0,999).execute().data or [])
        insights=(db.table("predictive_insights").select("customer_id,churn_risk_score,primary_churn_driver,recommended_product,prescriptive_action,evaluated_at").range(0,999).execute().data or [])
        by_customer={row["customer_id"]:row for row in insights}
        for customer in customers:
            insight=by_customer.get(customer["customer_id"]); customer["predictive_insights"]=[insight] if insight else []
        return {"customers":customers,"count":len(customers)}
    except Exception as exc:
        log.exception("Internal customer integration retrieval failed")
        raise HTTPException(500,"Unable to retrieve customer data") from exc

@app.get("/api/v1/explain/{customer_id}")
def explain(customer_id:str,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    authorize_staff(x_api_key,authorization)
    try:
        result=explain_customer(customer_id)
        if result is None: raise HTTPException(404,"Customer not found")
        return result
    except HTTPException: raise
    except Exception as exc:
        log.exception("Internal customer explanation failed")
        raise HTTPException(500,"Unable to retrieve explanation") from exc


from crm_api import router as crm_router
app.include_router(crm_router)

from management_api import router as management_router
from settings_api import router as settings_router
app.include_router(management_router)
app.include_router(settings_router)
