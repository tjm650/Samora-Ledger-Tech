from __future__ import annotations
import logging, os, secrets
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from analytics import run_pipeline, explain_customer
load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL","INFO"))
log=logging.getLogger("samora")
app=FastAPI(title="Samora Ledger Tech API",version="1.0.0")
origins=[x.strip() for x in os.getenv("API_CORS_ORIGINS","http://localhost:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=["GET","POST"],allow_headers=["Authorization","Content-Type","X-API-Key"])
def authorize(x_api_key: str|None):
    expected=os.getenv("API_KEY")
    if not expected: raise HTTPException(503,"API_KEY is not configured")
    if not x_api_key or not secrets.compare_digest(x_api_key,expected): raise HTTPException(401,"Invalid API key")
@app.get("/health")
def health(): return {"status":"ok","service":"samora-ledger-tech"}
@app.post("/api/v1/run-pipeline")
def pipeline(x_api_key: str|None=Header(default=None)):
    authorize(x_api_key)
    try:return {"status":"completed",**run_pipeline()}
    except Exception as exc:
        log.exception("Analytics pipeline failed")
        raise HTTPException(500,"Pipeline failed; inspect service logs") from exc
@app.get("/api/v1/explain/{customer_id}")
def explain(customer_id:str,x_api_key:str|None=Header(default=None)):
    authorize(x_api_key)
    try:
        result=explain_customer(customer_id)
        if result is None:raise HTTPException(404,"Customer not found")
        return result
    except HTTPException:raise
    except Exception as exc:
        log.exception("Customer explanation failed")
        raise HTTPException(500,"Unable to retrieve explanation") from exc
