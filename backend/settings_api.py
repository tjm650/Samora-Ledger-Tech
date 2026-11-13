from __future__ import annotations
import logging
import os
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from crm_api import _db, _staff, _demo_read, ALL_STAFF_ROLES

router=APIRouter(prefix="/api/v1/settings",tags=["workspace settings"])
log=logging.getLogger("samora.settings")

class PreferenceUpdate(BaseModel):
    preference_key:str=Field(min_length=1,max_length=100)
    preference_value:dict

class OrganisationSettingUpdate(BaseModel):
    organisation_id:str
    setting_key:str=Field(min_length=1,max_length=100)
    setting_value:dict

@router.get("/me")
def my_profile(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    actor=_staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        row=_db().table("staff_profiles").select("*").eq("user_id",actor["user_id"]).maybe_single().execute().data
        return row or {"user_id":actor["user_id"],"email":actor.get("email"),"role":actor["role"],"is_active":True}
    except Exception as exc:
        log.exception("Staff profile retrieval failed")
        raise HTTPException(500,"Unable to retrieve staff profile") from exc

@router.get("/preferences")
def get_preferences(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    if os.getenv("DEMO_PUBLIC_READS") == "true":
        _demo_read(x_api_key,authorization,ALL_STAFF_ROLES)
        return {"preferences": [], "demo_mode": True}
    actor=_staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        rows=_db().table("user_preferences").select("*").eq("user_id",actor["user_id"]).execute().data or []
        return {"preferences":rows}
    except Exception as exc:
        log.exception("User preferences retrieval failed")
        raise HTTPException(500,"Unable to retrieve user preferences") from exc

@router.patch("/preferences")
def update_preference(payload:PreferenceUpdate,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    actor=_staff(x_api_key,authorization,ALL_STAFF_ROLES)
    try:
        row={"user_id":actor["user_id"],"preference_key":payload.preference_key,"preference_value":payload.preference_value}
        result=_db().table("user_preferences").upsert(row,on_conflict="user_id,preference_key").execute().data
        return result[0] if result else row
    except Exception as exc:
        log.exception("User preference update failed")
        raise HTTPException(500,"Unable to save user preference") from exc

@router.get("/organisation")
def get_organisation_settings(x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    _staff(x_api_key,authorization,{"admin","executive"})
    try:
        rows=_db().table("organisation_settings").select("*").order("setting_key").execute().data or []
        return {"settings":rows}
    except Exception as exc:
        log.exception("Organisation settings retrieval failed")
        raise HTTPException(500,"Unable to retrieve organisation settings") from exc

@router.patch("/organisation")
def update_organisation_setting(payload:OrganisationSettingUpdate,x_api_key:str|None=Header(default=None),authorization:str|None=Header(default=None)):
    actor=_staff(x_api_key,authorization,{"admin"})
    try:
        db=_db()
        row={"organisation_id":payload.organisation_id,"setting_key":payload.setting_key,"setting_value":payload.setting_value,"updated_by":actor["user_id"]}
        previous=db.table("organisation_settings").select("*").eq("organisation_id",payload.organisation_id).eq("setting_key",payload.setting_key).maybe_single().execute().data
        result=db.table("organisation_settings").upsert(row,on_conflict="organisation_id,setting_key").execute().data
        saved=result[0] if result else row
        db.table("model_audit_logs").insert({"actor_user_id":actor["user_id"],"action":"organisation_setting_updated","entity_type":"organisation_setting","before_state":previous,"after_state":saved}).execute()
        return saved
    except Exception as exc:
        log.exception("Organisation setting update failed")
        raise HTTPException(500,"Unable to update organisation setting") from exc
