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
        debit30=recent[recent.transaction_type=="Debit"]
        debit60=d60[d60.transaction_type=="Debit"]
        debit90=d90[d90.transaction_type=="Debit"]
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
          "frequency_30d":count30,"monetary_spend_30d":round(float(debit30.amount.sum()),2),
          "monetary_spend_60d":round(float(debit60.amount.sum()),2),"monetary_spend_90d":round(float(debit90.amount.sum()),2),
          "average_transaction_value_90d":round(float(debit90.amount.mean()),2) if len(debit90) else 0.0,
          "balance_avg_30d":round(balance_avg,2),
          "velocity_score":round(velocity,4),"discretionary_spend_ratio":round(discretionary/total,5) if total else 0,
          "salary_disruption_flag":salary_disruption,"balance_drawdown_pct":round(drawdown,5),
          "behavior_segment":"salary_disrupted" if salary_disruption else ("engaged" if count30>=8 else "low_engagement"),
          "_salary_ever":prev_salary,"_balance_current":current,"_discretionary":discretionary})
    return pd.DataFrame(rows)

def score_customer(row, config=None):
    """Transparent heuristic churn score; not a probability or credit-risk estimate."""
    config=config or {}
    risk=float(config.get("base_score",8)); drivers=[]
    if row.salary_disruption_flag: risk+=float(config.get("salary_disruption_points",42)); drivers.append("Salary Deposit Ceased")
    if row.recency_days>14:
        risk+=min(float(config.get("maximum_recency_points",24)),(row.recency_days-14)*float(config.get("recency_points_per_day",1.2)))
        drivers.append("Recent Activity Declined")
    if row.velocity_score<0.65: risk+=float(config.get("velocity_decline_points",20)); drivers.append("Transaction Velocity Declined")
    if row.balance_avg_30d<250: risk+=float(config.get("low_balance_points",18)); drivers.append("Account Balance Near Zero")
    if row.balance_drawdown_pct>0.7: risk+=float(config.get("drawdown_points",12)); drivers.append("Significant Balance Drawdown")
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
    import time
    started_at=datetime.now(timezone.utc)
    started_clock=time.monotonic()
    url=os.environ["SUPABASE_URL"]; key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    db=create_client(url,key)
    customers=db.table("customers").select("customer_id").execute().data or []
    customer_ids=[x["customer_id"] for x in customers]
    transactions=[]
    # Keep each customer-ID filter small enough to avoid oversized PostgREST URLs.
    # Page each group in stable primary-key order because responses are capped.
    customer_batch_size=50
    page_size=1000
    for customer_start in range(0,len(customer_ids),customer_batch_size):
        customer_batch=customer_ids[customer_start:customer_start+customer_batch_size]
        offset=0
        while True:
            response=(db.table("transactions")
                .select("customer_id,timestamp,amount,transaction_type,merchant_category,post_transaction_balance")
                .in_("customer_id",customer_batch)
                .order("transaction_id")
                .range(offset,offset+page_size-1)
                .execute())
            page=response.data or []
            transactions.extend(page)
            if len(page)<page_size:
                break
            offset+=page_size
    frame=engineer_features(pd.DataFrame(transactions))
    if frame.empty: return {"customers_processed":0,"records_skipped":len(customer_ids)}
    config_rows=(db.table("model_configurations").select("configuration_value,version")
                 .eq("configuration_key","rules-v1-scoring-baseline")
                 .order("version",desc=True).limit(1).execute().data or [])
    scoring_config=config_rows[0]["configuration_value"] if config_rows else {}
    configuration_version=int(config_rows[0]["version"]) if config_rows else 0
    features=[]; insights=[]
    for row in frame.itertuples(index=False):
        data=row._asdict(); score=score_customer(row,scoring_config)
        features.append({k:data[k] for k in ("customer_id","recency_days","frequency_30d","monetary_spend_30d","monetary_spend_60d","monetary_spend_90d","average_transaction_value_90d","balance_avg_30d","velocity_score","discretionary_spend_ratio","salary_disruption_flag","balance_drawdown_pct","behavior_segment")})
        insights.append({"customer_id":data["customer_id"],**score})
    legacy_feature_fields=("customer_id","recency_days","frequency_30d","monetary_spend_90d","balance_avg_30d","velocity_score","discretionary_spend_ratio","salary_disruption_flag","balance_drawdown_pct","behavior_segment")
    for batch in range(0,len(features),250):
        legacy_rows=[{key:row[key] for key in legacy_feature_fields} for row in features[batch:batch+250]]
        db.table("customer_features").upsert(legacy_rows,on_conflict="customer_id").execute()
        db.table("predictive_insights").upsert(insights[batch:batch+250],on_conflict="customer_id").execute()

    # Append immutable feature and risk snapshots for audit and historical monitoring.
    evaluated_at=datetime.now(timezone.utc)
    version=(db.table("model_versions").select("model_version_id")
             .eq("version","rules-v1").maybe_single().execute().data or {})
    run_row={
        "model_version_id":version.get("model_version_id"),
        "status":"completed","customers_evaluated":len(features),"configuration_version":configuration_version,
        "records_skipped":max(0,len(customer_ids)-len(features)),"records_failed":0,
        "execution_duration_ms":int((time.monotonic()-started_clock)*1000),
        "started_at":started_at.isoformat(),"completed_at":evaluated_at.isoformat(),
        "metrics":None
    }
    run_result=db.table("model_runs").insert(run_row).execute().data
    model_run_id=run_result[0]["model_run_id"] if run_result else None

    previous_rows=(db.table("risk_score_history").select("customer_id,risk_score,risk_band,assessed_at")
                   .order("assessed_at",desc=True).range(0,9999).execute().data or [])
    previous_by_customer={}
    for old in previous_rows:
        previous_by_customer.setdefault(old["customer_id"],old)
    threshold_rows=db.table("risk_thresholds").select("significant_movement,low_max,moderate_max").eq("name","default").limit(1).execute().data or []
    threshold=threshold_rows[0] if threshold_rows else {"significant_movement":15,"low_max":29.99,"moderate_max":59.99}
    history_features=[]
    risk_history=[]
    alert_candidates=[]
    for feature, insight in zip(features, insights):
        history_features.append({
            "customer_id":feature["customer_id"],"calculated_at":evaluated_at.isoformat(),
            "feature_engine_version":"features-v1",
            **{key:feature.get(key) for key in (
                "recency_days","frequency_30d","monetary_spend_30d","monetary_spend_60d",
                "monetary_spend_90d","average_transaction_value_90d","balance_avg_30d",
                "balance_drawdown_pct","velocity_score","discretionary_spend_ratio",
                "salary_disruption_flag","behavior_segment"
            )}
        })
        score=float(insight["churn_risk_score"])
        band="high" if score>float(threshold["moderate_max"]) else ("moderate" if score>float(threshold["low_max"]) else "low")
        prior=previous_by_customer.get(feature["customer_id"])
        risk_history.append({
            "customer_id":feature["customer_id"],"risk_score":score,"risk_band":band,
            "primary_risk_driver":insight["primary_churn_driver"],
            "rules_engine_version":"rules-v1","configuration_version":configuration_version,"assessed_at":evaluated_at.isoformat(),
            "model_run_id":model_run_id
        })
        if prior:
            previous_score=float(prior["risk_score"])
            worsened=(prior["risk_band"]!="high" and band=="high") or (prior["risk_band"]=="low" and band=="moderate")
            moved_up=(score-previous_score)>=float(threshold["significant_movement"])
            if worsened or moved_up:
                alert_candidates.append({
                    "customer_id":feature["customer_id"],"alert_type":"band_increased" if worsened else "significant_increase",
                    "previous_score":previous_score,"current_score":score
                })
    for batch in range(0,len(history_features),250):
        db.table("customer_feature_history").insert(history_features[batch:batch+250]).execute()
    inserted_history=[]
    for batch in range(0,len(risk_history),250):
        inserted_history.extend(db.table("risk_score_history").insert(risk_history[batch:batch+250]).execute().data or [])
    history_id_by_customer={row["customer_id"]:row["risk_history_id"] for row in inserted_history}
    alerts=[]
    for item in alert_candidates:
        alerts.append({**item,"risk_history_id":history_id_by_customer.get(item["customer_id"])})
    for batch in range(0,len(alerts),250):
        db.table("risk_alerts").insert(alerts[batch:batch+250]).execute()
    return {"customers_processed":len(features),"insights_written":len(insights),
            "feature_snapshots_written":len(history_features),"risk_snapshots_written":len(risk_history),
            "risk_alerts_created":len(alerts),"rules_engine_version":"rules-v1",
            "model_run_id":model_run_id,"execution_duration_ms":run_row["execution_duration_ms"]}


def explain_customer(customer_id):
    from supabase import create_client
    db=create_client(os.environ["SUPABASE_URL"],os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    customer=db.table("customers").select("*").eq("customer_id",customer_id).maybe_single().execute().data
    if not customer:return None
    features=db.table("customer_features").select("*").eq("customer_id",customer_id).maybe_single().execute().data
    insight=db.table("predictive_insights").select("*").eq("customer_id",customer_id).maybe_single().execute().data
    return {"customer":customer,"features":features,"insight":insight,"explanation_type":"transparent rule contributions; not SHAP"}
