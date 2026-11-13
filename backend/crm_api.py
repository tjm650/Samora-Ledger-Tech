from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
import logging
import os

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["CRM and risk"])
log = logging.getLogger("samora.crm")
CRM_ROLES = {"admin", "analyst", "relationship_manager"}
ALL_STAFF_ROLES = CRM_ROLES | {"executive"}

def _db():
    from supabase import create_client
    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise HTTPException(503, "Database connection is not configured")
    return create_client(url, key)

def _staff(x_api_key: str | None, authorization: str | None, roles=CRM_ROLES):
    import secrets
    expected = os.getenv("API_KEY")
    if not expected or not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid API key")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Staff sign-in required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(401, "Staff sign-in required")
    try:
        user = _db().auth.get_user(token).user
    except Exception as exc:
        raise HTTPException(401, "Staff session is invalid or expired") from exc
    if not user:
        raise HTTPException(401, "Staff session is invalid or expired")
    metadata = getattr(user, "app_metadata", None) or {}
    role = metadata.get("role")
    if role not in roles:
        raise HTTPException(403, "Your staff role is not permitted to perform this action")
    actor={"user_id":str(user.id),"role":role,"email":getattr(user,"email",None)}
    try:
        _db().table("staff_profiles").upsert({
            "user_id":actor["user_id"],"email":actor["email"],
            "display_name":(getattr(user,"user_metadata",None) or {}).get("full_name"),
            "role":role,"is_active":True
        },on_conflict="user_id").execute()
    except Exception as exc:
        log.exception("Staff profile synchronisation failed")
        raise HTTPException(503,"Staff profile is not provisioned in the database") from exc
    return actor

class InteractionCreate(BaseModel):
    interaction_type: Literal["call", "email", "meeting", "branch_visit", "message", "other"]
    subject: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=10000)
    outcome: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None

class TaskCreate(BaseModel):
    customer_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    assigned_to: UUID | None = None
    due_at: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)

class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    status: Literal["open", "in_progress", "completed", "cancelled"] | None = None
    assigned_to: UUID | None = None
    due_at: datetime | None = None
    outcome: str | None = Field(default=None, max_length=2000)

class AlertPatch(BaseModel):
    status: Literal["acknowledged", "resolved"]
    resolution_note: str | None = Field(default=None, max_length=2000)

@router.get("/crm/customers")
def crm_customers(
    search: str | None = Query(default=None, max_length=200),
    account_tier: Literal["Standard", "Gold", "Platinum"] | None = None,
    risk_band: Literal["low", "moderate", "high"] | None = None,
    segment: str | None = Query(default=None, max_length=80),
    created_from: date | None = None,
    created_to: date | None = None,
    sort_by: Literal["name", "risk_score", "account_tier", "created_at"] = "name",
    sort_dir: Literal["asc", "desc"] = "asc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    if created_from and created_to and created_from > created_to:
        raise HTTPException(422, "created_from must not be after created_to")
    try:
        result = _db().rpc("crm_customer_directory", {
            "p_search": search, "p_account_tier": account_tier, "p_risk_band": risk_band,
            "p_segment": segment, "p_created_from": created_from.isoformat() if created_from else None,
            "p_created_to": created_to.isoformat() if created_to else None,
            "p_sort_by": sort_by, "p_sort_dir": sort_dir, "p_page": page, "p_page_size": page_size,
        }).execute().data
        return result if isinstance(result, dict) else (result[0] if result else {"customers": [], "total": 0, "page": page, "page_size": page_size})
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("CRM directory query failed")
        raise HTTPException(500, "Unable to retrieve CRM customer directory") from exc

@router.get("/crm/customers/{customer_id}")
def crm_customer_profile(
    customer_id: UUID,
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        db = _db()
        customer = db.table("customers").select("customer_id,full_name,email,account_tier,created_at").eq("customer_id", str(customer_id)).maybe_single().execute().data
        if not customer:
            raise HTTPException(404, "Customer not found")
        features = db.table("customer_features").select("*").eq("customer_id", str(customer_id)).maybe_single().execute().data
        insight = db.table("predictive_insights").select("*").eq("customer_id", str(customer_id)).maybe_single().execute().data
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        tx = db.table("transactions").select("timestamp,amount,transaction_type,post_transaction_balance").eq("customer_id", str(customer_id)).gte("timestamp", since).order("timestamp", desc=True).limit(5000).execute().data or []
        now = datetime.now(timezone.utc)
        spend = {}
        for days in (30, 60, 90):
            cut = now - timedelta(days=days)
            spend[str(days)] = round(sum(float(t["amount"]) for t in tx if t["transaction_type"] == "Debit" and datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00")) >= cut), 2)
        transaction_values = [float(t["amount"]) for t in tx]
        latest_balance = float(tx[0]["post_transaction_balance"]) if tx else None
        profile = {
            "customer": customer, "features": features, "insight": insight,
            "spending": {"30d": spend["30"], "60d": spend["60"], "90d": spend["90"]},
            "transaction_metrics": {
                "transaction_count_90d": len(tx),
                "average_transaction_value_90d": round(sum(transaction_values) / len(transaction_values), 2) if transaction_values else 0,
                "latest_recorded_balance": latest_balance,
                "transaction_recency_days": features.get("recency_days") if features else None,
            },
            "assessment_timestamp": insight.get("evaluated_at") if insight else None,
            "explanation_type": "transparent rules-based churn assessment; not credit risk or SHAP",
        }
        return profile
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("CRM customer profile retrieval failed")
        raise HTTPException(500, "Unable to retrieve customer profile") from exc

@router.post("/crm/customers/{customer_id}/interactions", status_code=201)
def create_interaction(customer_id: UUID, payload: InteractionCreate, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    actor = _staff(x_api_key, authorization)
    try:
        db = _db()
        row = {"customer_id": str(customer_id), "staff_user_id": actor["user_id"], **payload.model_dump(exclude_none=True)}
        if row.get("occurred_at"): row["occurred_at"] = row["occurred_at"].isoformat()
        result = db.table("crm_interactions").insert(row).execute().data
        if not result: raise HTTPException(500, "Interaction was not saved")
        return result[0]
    except HTTPException: raise
    except Exception as exc:
        log.exception("CRM interaction creation failed")
        raise HTTPException(500, "Unable to record customer interaction") from exc

@router.get("/crm/customers/{customer_id}/interactions")
def list_interactions(customer_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        result = _db().table("crm_interactions").select("*", count="exact").eq("customer_id", str(customer_id)).order("occurred_at", desc=True).range((page-1)*page_size, page*page_size-1).execute()
        return {"interactions": result.data or [], "total": result.count or 0, "page": page, "page_size": page_size}
    except Exception as exc:
        log.exception("CRM interaction history retrieval failed")
        raise HTTPException(500, "Unable to retrieve interaction history") from exc

@router.post("/crm/tasks", status_code=201)
def create_task(payload: TaskCreate, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    actor = _staff(x_api_key, authorization)
    try:
        db = _db()
        row = payload.model_dump(exclude_none=True)
        row["customer_id"] = str(row["customer_id"])
        if row.get("assigned_to"): row["assigned_to"] = str(row["assigned_to"])
        if row.get("due_at"): row["due_at"] = row["due_at"].isoformat()
        row["created_by"] = actor["user_id"]
        result = db.table("crm_tasks").insert(row).execute().data
        if not result: raise HTTPException(500, "Task was not saved")
        task = result[0]
        db.table("crm_task_history").insert({"task_id": task["task_id"], "actor_user_id": actor["user_id"], "event_type": "created", "new_values": task}).execute()
        return task
    except HTTPException: raise
    except Exception as exc:
        log.exception("CRM task creation failed")
        raise HTTPException(500, "Unable to create CRM task") from exc

@router.get("/crm/tasks")
def list_tasks(status: Literal["open", "in_progress", "completed", "cancelled"] | None = None, assigned_to: UUID | None = None, customer_id: UUID | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        q = _db().table("crm_tasks").select("*", count="exact")
        if status: q = q.eq("status", status)
        if assigned_to: q = q.eq("assigned_to", str(assigned_to))
        if customer_id: q = q.eq("customer_id", str(customer_id))
        result = q.order("due_at").range((page-1)*page_size, page*page_size-1).execute()
        return {"tasks": result.data or [], "total": result.count or 0, "page": page, "page_size": page_size}
    except Exception as exc:
        log.exception("CRM task listing failed")
        raise HTTPException(500, "Unable to retrieve CRM tasks") from exc

@router.get("/crm/customers/{customer_id}/tasks")
def customer_tasks(customer_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        result = _db().table("crm_tasks").select("*", count="exact").eq("customer_id", str(customer_id)).order("created_at", desc=True).range((page-1)*page_size, page*page_size-1).execute()
        return {"tasks": result.data or [], "total": result.count or 0, "page": page, "page_size": page_size}
    except Exception as exc:
        log.exception("Customer task retrieval failed")
        raise HTTPException(500, "Unable to retrieve customer tasks") from exc

@router.patch("/crm/tasks/{task_id}")
def update_task(task_id: UUID, payload: TaskPatch, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    actor = _staff(x_api_key, authorization)
    changes = payload.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, "At least one task field must be supplied")
    if changes.get("assigned_to"): changes["assigned_to"] = str(changes["assigned_to"])
    if changes.get("due_at"): changes["due_at"] = changes["due_at"].isoformat()
    changes["updated_at"] = datetime.now(timezone.utc).isoformat()
    if changes.get("status") == "completed": changes["completed_at"] = datetime.now(timezone.utc).isoformat()
    try:
        db = _db()
        old = db.table("crm_tasks").select("*").eq("task_id", str(task_id)).maybe_single().execute().data
        if not old: raise HTTPException(404, "Task not found")
        result = db.table("crm_tasks").update(changes).eq("task_id", str(task_id)).execute().data
        new = result[0] if result else {**old, **changes}
        db.table("crm_task_history").insert({"task_id": str(task_id), "actor_user_id": actor["user_id"], "event_type": "updated", "old_values": old, "new_values": new}).execute()
        return new
    except HTTPException: raise
    except Exception as exc:
        log.exception("CRM task update failed")
        raise HTTPException(500, "Unable to update CRM task") from exc

@router.get("/risk/summary")
def risk_summary(x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        db = _db()
        rows = db.table("predictive_insights").select("churn_risk_score,primary_churn_driver,evaluated_at").range(0,9999).execute().data or []
        threshold_rows = db.table("risk_thresholds").select("low_max,moderate_max").eq("name","default").limit(1).execute().data or []
        threshold = threshold_rows[0] if threshold_rows else {"low_max":29.99,"moderate_max":59.99}
        low_max, moderate_max = float(threshold["low_max"]), float(threshold["moderate_max"])
        scores = [float(r["churn_risk_score"]) for r in rows]
        return {"assessment_type": "rules_based_churn_risk_not_credit_risk", "customers_assessed": len(scores),
                "average_score": round(sum(scores)/len(scores), 2) if scores else 0,
                "low": sum(s <= low_max for s in scores), "moderate": sum(low_max < s <= moderate_max for s in scores),
                "high": sum(s > moderate_max for s in scores), "thresholds":{"low_max":low_max,"moderate_max":moderate_max},
                "generated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        log.exception("Risk summary retrieval failed")
        raise HTTPException(500, "Unable to retrieve risk summary") from exc

@router.get("/risk/trends")
def risk_trends(days: int = Query(90, ge=7, le=730), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        cutoff = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        rows = _db().table("risk_score_history").select("assessed_at,risk_score,risk_band").gte("assessed_at", cutoff).order("assessed_at").range(0,9999).execute().data or []
        return {"days": days, "history_available": bool(rows), "observations": rows}
    except Exception as exc:
        log.exception("Risk trend retrieval failed")
        raise HTTPException(500, "Unable to retrieve risk trends") from exc

@router.get("/risk/alerts")
def risk_alerts(status: Literal["open", "acknowledged", "resolved"] | None = "open", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        q = _db().table("risk_alerts").select("*", count="exact")
        if status: q = q.eq("status", status)
        result = q.order("created_at", desc=True).range((page-1)*page_size, page*page_size-1).execute()
        return {"alerts": result.data or [], "total": result.count or 0, "page": page, "page_size": page_size}
    except Exception as exc:
        log.exception("Risk alert retrieval failed")
        raise HTTPException(500, "Unable to retrieve risk alerts") from exc

@router.patch("/risk/alerts/{alert_id}")
def update_risk_alert(alert_id: UUID, payload: AlertPatch, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    actor = _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    now = datetime.now(timezone.utc).isoformat()
    changes = {"status": payload.status}
    if payload.status == "acknowledged": changes.update({"acknowledged_by": actor["user_id"], "acknowledged_at": now})
    else: changes.update({"resolved_by": actor["user_id"], "resolved_at": now, "resolution_note": payload.resolution_note})
    try:
        result = _db().table("risk_alerts").update(changes).eq("alert_id", str(alert_id)).execute().data
        if not result: raise HTTPException(404, "Risk alert not found")
        return result[0]
    except HTTPException: raise
    except Exception as exc:
        log.exception("Risk alert update failed")
        raise HTTPException(500, "Unable to update risk alert") from exc

@router.get("/risk/customers/{customer_id}/history")
def customer_risk_history(customer_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        result = _db().table("risk_score_history").select("*", count="exact").eq("customer_id", str(customer_id)).order("assessed_at", desc=True).range((page-1)*page_size, page*page_size-1).execute()
        return {"history": result.data or [], "total": result.count or 0, "page": page, "page_size": page_size}
    except Exception as exc:
        log.exception("Customer risk history retrieval failed")
        raise HTTPException(500, "Unable to retrieve customer risk history") from exc


class RiskThresholdUpdate(BaseModel):
    low_max: float = Field(ge=0, lt=100)
    moderate_max: float = Field(gt=0, le=100)
    significant_movement: float = Field(gt=0, le=100)

@router.get("/risk/thresholds")
def get_risk_thresholds(x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        rows = _db().table("risk_thresholds").select("*").order("name").execute().data or []
        return {"thresholds": rows}
    except Exception as exc:
        log.exception("Risk threshold retrieval failed")
        raise HTTPException(500, "Unable to retrieve risk thresholds") from exc

@router.patch("/risk/thresholds/{threshold_id}")
def update_risk_thresholds(threshold_id: UUID, payload: RiskThresholdUpdate, x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    actor = _staff(x_api_key, authorization, {"admin"})
    if payload.moderate_max <= payload.low_max:
        raise HTTPException(422, "moderate_max must be greater than low_max")
    try:
        db = _db()
        old = db.table("risk_thresholds").select("*").eq("threshold_id", str(threshold_id)).maybe_single().execute().data
        if not old: raise HTTPException(404, "Risk threshold configuration not found")
        changes = {**payload.model_dump(), "configured_by": actor["user_id"], "updated_at": datetime.now(timezone.utc).isoformat()}
        result = db.table("risk_thresholds").update(changes).eq("threshold_id", str(threshold_id)).execute().data
        saved = result[0] if result else {**old, **changes}
        db.table("model_audit_logs").insert({
            "actor_user_id": actor["user_id"], "action": "risk_thresholds_updated",
            "entity_type": "risk_threshold", "entity_id": str(threshold_id),
            "before_state": old, "after_state": saved
        }).execute()
        return saved
    except HTTPException: raise
    except Exception as exc:
        log.exception("Risk threshold update failed")
        raise HTTPException(500, "Unable to update risk thresholds") from exc


@router.get("/crm/tasks/{task_id}/history")
def task_history(task_id: UUID, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100), x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, ALL_STAFF_ROLES)
    try:
        result = _db().table("crm_task_history").select("*", count="exact").eq("task_id", str(task_id)).order("created_at", desc=True).range((page-1)*page_size, page*page_size-1).execute()
        return {"history": result.data or [], "total": result.count or 0, "page": page, "page_size": page_size}
    except Exception as exc:
        log.exception("CRM task history retrieval failed")
        raise HTTPException(500, "Unable to retrieve task history") from exc

@router.get("/crm/staff")
def list_staff(x_api_key: str | None = Header(default=None), authorization: str | None = Header(default=None)):
    _staff(x_api_key, authorization, {"admin", "analyst", "relationship_manager"})
    try:
        rows = _db().table("staff_profiles").select("user_id,display_name,email,role").eq("is_active", True).order("display_name").execute().data or []
        return {"staff": rows}
    except Exception as exc:
        log.exception("CRM staff directory retrieval failed")
        raise HTTPException(500, "Unable to retrieve staff directory") from exc
