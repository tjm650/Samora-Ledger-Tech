from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from io import StringIO
import csv
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from crm_api import _db, _staff, ALL_STAFF_ROLES

router = APIRouter(prefix="/api/v1", tags=["reports and governance"])
log = logging.getLogger("samora.management")

class ReportRequest(BaseModel):
    report_key: Literal["executive_summary","transaction_performance","churn_risk","customer_segmentation","risk_drivers"]
    period_start: date
    period_end: date
    parameters: dict = Field(default_factory=dict)

class ConfigurationUpdate(BaseModel):
    configuration_key: str = Field(min_length=1, max_length=100)
    configuration_value: dict

@router.post("/reports/generate", status_code=201)
def generate_report(payload: ReportRequest, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    actor = _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    if payload.period_end < payload.period_start:
        raise HTTPException(422, "period_end must not be before period_start")
    try:
        db = _db()
        start = datetime.combine(payload.period_start, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(payload.period_end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        overview=db.rpc("analytics_period_summary",{
            "p_start":start.isoformat(),"p_end":end.isoformat(),
            "p_interval":"day","p_dimension":"none"
        }).execute().data
        if isinstance(overview,list) and overview: overview=overview[0]
        if not isinstance(overview,dict): raise HTTPException(500,"Analytics report aggregation returned an invalid result")
        if payload.report_key=="transaction_performance":
            content={"metrics":overview["metrics"],"transaction_trend":overview["transaction_trend"],"category_breakdown":overview["category_breakdown"],"channel_breakdown":overview["channel_breakdown"]}
        elif payload.report_key=="churn_risk":
            content={"risk_metrics":overview["risk_metrics"],"metrics":overview["metrics"]}
        elif payload.report_key=="customer_segmentation":
            customers=db.table("customers").select("account_tier").range(0,9999).execute().data or []
            features=db.table("customer_features").select("behavior_segment").range(0,9999).execute().data or []
            from collections import Counter
            content={"account_tier_distribution":dict(Counter(x["account_tier"] for x in customers)),"behavioral_segments":dict(Counter(x.get("behavior_segment") or "unclassified" for x in features))}
        elif payload.report_key=="risk_drivers":
            content={"risk_metrics":overview["risk_metrics"]}
        else:
            content={"metrics":overview["metrics"],"risk_metrics":overview["risk_metrics"],"transaction_trend":overview["transaction_trend"]}
        definitions=db.table("report_definitions").select("report_definition_id").eq("report_key",payload.report_key).maybe_single().execute().data or {}
        config_rows=db.table("model_configurations").select("version").eq("configuration_key","rules-v1-scoring-baseline").order("version",desc=True).limit(1).execute().data or []
        configuration_version=int(config_rows[0]["version"]) if config_rows else 0
        run={
            "report_definition_id":definitions.get("report_definition_id"),"report_key":payload.report_key,
            "requested_by":actor["user_id"],"period_start":payload.period_start.isoformat(),
            "period_end":payload.period_end.isoformat(),"status":"completed",
            "analytics_version":"rules-v1","configuration_version":configuration_version,"data_cutoff_at":datetime.now(timezone.utc).isoformat(),
            "parameters":payload.parameters
        }
        created=db.table("report_runs").insert(run).execute().data
        if not created: raise HTTPException(500,"Report run could not be persisted")
        report=created[0]
        db.table("report_snapshots").insert({"report_id":report["report_id"],"section_key":"report_content","content":content}).execute()
        return {**report,"content":content}
    except HTTPException: raise
    except Exception as exc:
        log.exception("Report generation failed")
        raise HTTPException(500,"Unable to generate and persist report") from exc

@router.get("/reports")
def list_reports(page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        result=_db().table("report_runs").select("*",count="exact").order("generated_at",desc=True).range((page-1)*page_size,page*page_size-1).execute()
        return {"reports":result.data or [],"total":result.count or 0,"page":page,"page_size":page_size}
    except Exception as exc:
        log.exception("Report listing failed")
        raise HTTPException(500,"Unable to retrieve reports") from exc

@router.get("/reports/{report_id}")
def get_report(report_id:UUID,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        db=_db()
        report=db.table("report_runs").select("*").eq("report_id",str(report_id)).maybe_single().execute().data
        if not report: raise HTTPException(404,"Report not found")
        snapshots=db.table("report_snapshots").select("section_key,content,created_at").eq("report_id",str(report_id)).execute().data or []
        return {**report,"snapshots":snapshots}
    except HTTPException: raise
    except Exception as exc:
        log.exception("Report detail retrieval failed")
        raise HTTPException(500,"Unable to retrieve report") from exc

@router.get("/reports/{report_id}/download")
def download_report(report_id:UUID,format:Literal["csv"]="csv",x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        db=_db()
        report=db.table("report_runs").select("*").eq("report_id",str(report_id)).maybe_single().execute().data
        if not report: raise HTTPException(404,"Report not found")
        snapshots=db.table("report_snapshots").select("content").eq("report_id",str(report_id)).execute().data or []
        content=snapshots[0].get("content",{}) if snapshots else {}
        stream=StringIO(); writer=csv.writer(stream); writer.writerow(["section","metric","value"])
        for section,value in content.items():
            if isinstance(value,list):
                for index,item in enumerate(value):
                    writer.writerow([section,index,str(item)])
            elif isinstance(value,dict):
                for key,item in value.items(): writer.writerow([section,key,str(item)])
            else: writer.writerow([section,"value",str(value)])
        filename=f"samora-{report['report_key']}-{report_id}.csv"
        return Response(content=stream.getvalue(),media_type="text/csv",headers={"Content-Disposition":f'attachment; filename="{filename}"'})
    except HTTPException: raise
    except Exception as exc:
        log.exception("Report export failed")
        raise HTTPException(500,"Unable to export report") from exc

@router.get("/governance/models")
def governance_models(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        rows=_db().table("model_versions").select("*").order("created_at",desc=True).execute().data or []
        return {"models":rows,"evaluation_metrics_available":False,"metrics_note":"No validated labelled churn outcome dataset is registered; model performance metrics are not reported."}
    except Exception as exc:
        log.exception("Model registry retrieval failed")
        raise HTTPException(500,"Unable to retrieve model registry") from exc

@router.get("/governance/runs")
def governance_runs(page:int=Query(1,ge=1),page_size:int=Query(25,ge=1,le=100),x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        result=_db().table("model_runs").select("*",count="exact").order("started_at",desc=True).range((page-1)*page_size,page*page_size-1).execute()
        return {"runs":result.data or [],"total":result.count or 0,"page":page,"page_size":page_size}
    except Exception as exc:
        log.exception("Model run history retrieval failed")
        raise HTTPException(500,"Unable to retrieve model runs") from exc

@router.get("/governance/configuration")
def governance_configuration(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        rows=_db().table("model_configurations").select("*").order("configuration_key").order("version",desc=True).execute().data or []
        thresholds=_db().table("risk_thresholds").select("*").order("name").execute().data or []
        return {"configurations":rows,"risk_thresholds":thresholds}
    except Exception as exc:
        log.exception("Model configuration retrieval failed")
        raise HTTPException(500,"Unable to retrieve model configuration") from exc

@router.patch("/governance/configuration")
def update_governance_configuration(payload:ConfigurationUpdate,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    actor=_staff(x_api_key,authorization,{"admin"})
    if payload.configuration_key=="rules-v1-scoring-baseline":
        allowed={"base_score","salary_disruption_points","maximum_recency_points","recency_points_per_day","velocity_decline_points","low_balance_points","drawdown_points"}
        if not allowed.issubset(payload.configuration_value):
            raise HTTPException(422,"Scoring configuration is missing required numeric fields")
        try:
            values={key:float(payload.configuration_value[key]) for key in allowed}
        except (TypeError,ValueError):
            raise HTTPException(422,"Scoring configuration values must be numeric")
        if any(value<0 or value>100 for value in values.values()):
            raise HTTPException(422,"Scoring configuration values must be between 0 and 100")
    try:
        db=_db()
        previous=db.table("model_configurations").select("*").eq("configuration_key",payload.configuration_key).order("version",desc=True).limit(1).execute().data or []
        version=(int(previous[0]["version"])+1) if previous else 1
        row={"configuration_key":payload.configuration_key,"configuration_value":payload.configuration_value,"version":version,"changed_by":actor["user_id"]}
        created=db.table("model_configurations").insert(row).execute().data
        db.table("model_audit_logs").insert({"actor_user_id":actor["user_id"],"action":"configuration_updated","entity_type":"model_configuration","entity_id":created[0]["configuration_id"],"before_state":previous[0] if previous else None,"after_state":created[0]}).execute()
        return created[0]
    except Exception as exc:
        log.exception("Model configuration update failed")
        raise HTTPException(500,"Unable to update model configuration") from exc

@router.get("/governance/audit-logs")
def governance_audit_logs(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,{"admin","executive"})
    try:
        result=_db().table("model_audit_logs").select("*",count="exact").order("created_at",desc=True).range((page-1)*page_size,page*page_size-1).execute()
        return {"audit_logs":result.data or [],"total":result.count or 0,"page":page,"page_size":page_size}
    except Exception as exc:
        log.exception("Governance audit log retrieval failed")
        raise HTTPException(500,"Unable to retrieve governance audit logs") from exc
