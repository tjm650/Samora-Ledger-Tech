"""Feature engineering and transparent baseline scoring for Samora Ledger Tech."""
from __future__ import annotations
import os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
ESSENTIAL={"Groceries","Utilities","ATM","Transfers"}
DISCRETIONARY={"Travel","Luxury"}

def engineer_features(transactions: pd.DataFrame, now=None) -> pd.DataFrame:
    now=pd.Timestamp(now or datetime.now(timezone.utc))
    if transactions.empty: return pd.DataFrame()
    tx=transactions.copy()
    tx["timestamp"]=pd.to_datetime(tx["timestamp"],utc=True)
    tx["amount"]=pd.to_numeric(tx["amount"],errors="coerce").fillna(0)
    tx["post_transaction_balance"]=pd.to_numeric(tx["post_transaction_balance"],errors="coerce").fillna(0)
    rows=[]
    for cid,g in tx.groupby("customer_id"):
        g=g.sort_values("timestamp"); recent=g[g.timestamp>=now-pd.Timedelta(days=30)]
        d60=g[g.timestamp>=now-pd.Timedelta(days=60)]; d90=g[g.timestamp>=now-pd.Timedelta(days=90)]
        debits=d90[d90.transaction_type=="Debit"]
        salary=g[(g.merchant_category=="Salary")&(g.transaction_type=="Credit")]
        last_salary=salary.timestamp.max() if not salary.empty else None
        salary_disruption=bool(not salary.empty and (now-last_salary).days>35)
        prev_salary=bool(len(salary)>0)
        count30=len(recent); count90=len(d90)
        velocity=float(count30/max(count90/3,1))
        discretionary=float(debits[debits.merchant_category.isin(DISCRETIONARY)].amount.sum())
        total=float(debits.amount.sum())
        balances=recent.post_transaction_balance
        balance_avg=float(balances.mean()) if len(balances) else float(g.post_transaction_balance.tail(1).mean())
        all_bal=g.post_transaction_balance
        peak=float(all_bal.max()) if len(all_bal) else 0
        current=float(all_bal.iloc[-1]) if len(all_bal) else 0
        drawdown=max(0.0,(peak-current)/peak) if peak>0 else 0.0
        rows.append({"customer_id":str(cid),"recency_days":int((now-g.timestamp.max()).days),
          "frequency_30d":count30,"monetary_spend_90d":round(total,2),"balance_avg_30d":round(balance_avg,2),
          "velocity_score":round(velocity,4),"discretionary_spend_ratio":round(discretionary/total,5) if total else 0,
          "salary_disruption_flag":salary_disruption,"balance_drawdown_pct":round(drawdown,5),
          "behavior_segment":"salary_disrupted" if salary_disruption else ("engaged" if count30>=8 else "low_engagement"),
          "_salary_ever":prev_salary,"_balance_current":current,"_discretionary":discretionary})
    return pd.DataFrame(rows)

def score_customer(row):
    """Explainable baseline probability; replace synthetic proxy with validated labels for production."""
    risk=8.0; drivers=[]
    if row.salary_disruption_flag: risk+=42; drivers.append("Salary Deposit Ceased")
    if row.recency_days>14: risk+=min(24,(row.recency_days-14)*1.2); drivers.append("Recent Activity Declined")
    if row.velocity_score<0.65: risk+=20; drivers.append("Transaction Velocity Declined")
    if row.balance_avg_30d<250: risk+=18; drivers.append("Account Balance Near Zero")
    if row.balance_drawdown_pct>0.7: risk+=12; drivers.append("Significant Balance Drawdown")
    risk=float(np.clip(risk,0,100))
    balance=float(row.balance_avg_30d); freq=int(row.frequency_30d); ratio=float(row.discretionary_spend_ratio)
    if balance>5000 and ratio>=.25: product="Platinum Travel Card"
    elif balance>5000 and freq<12: product="High-Yield Savings"
    elif not row.salary_disruption_flag and freq>=5: product="Investment & Wealth Management"
    else: product="Everyday Banking Bundle"
    action=("Call within one business day; confirm salary routing and cash-flow needs, then agree a tailored retention plan."
      if risk>=60 else "Offer a product suitability review and a consent-based relationship check-in.")
    return {"churn_risk_score":round(risk,2),"primary_churn_driver":drivers[0] if drivers else "No material risk signal",
      "recommended_product":product,"prescriptive_action":action}

def run_pipeline():
    from supabase import create_client
    url=os.environ["SUPABASE_URL"]; key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    db=create_client(url,key)
    customers=db.table("customers").select("customer_id").execute().data or []
    customer_ids=[x["customer_id"] for x in customers]
    transactions=[]
    # Fetch transactions in bounded pages instead of issuing one HTTP request per customer.
    # PostgREST commonly caps responses at 1,000 rows, so page explicitly and order
    # by the primary key to keep pagination stable.
    page_size=1000
    offset=0
    while True:
        response=(db.table("transactions")
            .select("customer_id,timestamp,amount,transaction_type,merchant_category,post_transaction_balance")
            .in_("customer_id",customer_ids)
            .order("transaction_id")
            .range(offset,offset+page_size-1)
            .execute())
        page=response.data or []
        transactions.extend(page)
        if len(page)<page_size:
            break
        offset+=page_size
    frame=engineer_features(pd.DataFrame(transactions))
    if frame.empty: return {"customers_processed":0}
    features=[]; insights=[]
    for row in frame.itertuples(index=False):
        data=row._asdict(); score=score_customer(row)
        features.append({k:data[k] for k in ("customer_id","recency_days","frequency_30d","monetary_spend_90d","balance_avg_30d","velocity_score","discretionary_spend_ratio","salary_disruption_flag","balance_drawdown_pct","behavior_segment")})
        insights.append({"customer_id":data["customer_id"],**score})
    for batch in range(0,len(features),250):
        db.table("customer_features").upsert(features[batch:batch+250],on_conflict="customer_id").execute()
        db.table("predictive_insights").upsert(insights[batch:batch+250],on_conflict="customer_id").execute()
    return {"customers_processed":len(features),"insights_written":len(insights)}

def explain_customer(customer_id):
    from supabase import create_client
    db=create_client(os.environ["SUPABASE_URL"],os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    customer=db.table("customers").select("*").eq("customer_id",customer_id).maybe_single().execute().data
    if not customer:return None
    features=db.table("customer_features").select("*").eq("customer_id",customer_id).maybe_single().execute().data
    insight=db.table("predictive_insights").select("*").eq("customer_id",customer_id).maybe_single().execute().data
    return {"customer":customer,"features":features,"insight":insight,"explanation_type":"transparent rule contributions; not SHAP"}
