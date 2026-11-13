# Samora Ledger Tech
Enterprise Banking Transaction Analytics & Executive Decision-Support MVP.

## Source layout
- `database/schema.sql` — Supabase PostgreSQL tables, constraints, indexes and RLS.
- `backend/` — Python 3.11 FastAPI service, synthetic data seeder and analytics pipeline.
- `frontend/` — Next.js App Router executive workspace: overview, transaction activity, risk and exposure, analytics and trends, management reports, and model governance. The website is designed for banking executive staff and does not expose a CRM or customer portfolio interface.
- `render.yaml` — Render deployment blueprint.
- `.github/workflows/ci.yml` — backend tests and frontend type-check workflow.

## Local setup
1. Create a disposable Supabase project and apply `database/schema.sql` in the SQL editor.
2. Copy `backend/.env.example` to `backend/.env`, set the project URL and service-role key. Never expose the service-role key to the browser.
3. From `backend`: `python -m venv .venv && pip install -r requirements.txt`; run `ALLOW_DEMO_SEEDING=true python data_seeder.py` only on a disposable demo database; start API with `uvicorn main:app --reload`.
4. Copy `frontend/.env.example` to `frontend/.env.local`, set `SAMORA_API_URL` to the Render service base URL and `SAMORA_API_KEY` to the Render `API_KEY` value, then from `frontend`: `npm install && npm run dev`. Keep both Render variables server-side (never prefix them with `NEXT_PUBLIC_`). Also configure `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` for the executive staff sign-in flow.
5. Configure `API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and allowed CORS origins in Render. In Vercel, set root directory to `frontend`; configure server-side `SAMORA_API_URL` and `SAMORA_API_KEY` with the Render service URL and Render `API_KEY` value; and configure `NEXT_PUBLIC_SUPABASE_URL` plus `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` for staff sign-in. Never expose the Render API key or Supabase service-role key in browser variables.
6. Create staff accounts through the trusted Supabase Auth administration process and assign an approved `app_metadata.role`: `executive`, `admin`, `analyst`, or `relationship_manager`. The website has no public registration. Role metadata must be assigned by a trusted administrator, never through user-editable metadata.

## API
- `GET /health`
- `GET /api/v1/executive/overview?period_days=90` with `X-API-Key` — aggregated executive metrics and trends.
- `GET /api/v1/executive/transactions?limit=50&offset=0` with `X-API-Key` — paginated ledger activity.
- `POST /api/v1/run-pipeline` with `X-API-Key`.
- `GET /api/v1/customers` and `GET /api/v1/explain/{customer_id}` remain internal compatibility endpoints and are not exposed in the executive website.

## Executive access and security
The Next.js workspace uses Supabase Auth cookie sessions and checks trusted `app_metadata.role` claims on both page requests and API routes. Only approved staff roles can access the workspace. Server-side Render API credentials remain private. The API proxy uses the Render service's service-role access only after verifying an authenticated, authorised staff identity.

## Important model and security limitations
This MVP uses transparent rule-based risk scoring rather than a trained production classifier. It does not estimate revenue-at-risk because account margin/revenue data is not part of the requested schema. Explanations are not SHAP values. Synthetic cohort patterns are not validated churn labels. Before real use, replace the scoring baseline with outcome-labelled temporal model training, calibration, independent validation, fairness and drift testing, governance, access review and human oversight. Product offers require suitability, eligibility and consent controls. Restrict staff roles through trusted Supabase `app_metadata`; never grant those roles from user-editable metadata. Seeder is demo-only and must never run against production customer data.

## Validation
CI installs backend dependencies and compiles the Python service; frontend CI runs TypeScript type-check. Live Supabase, Render and Vercel deployment require your project credentials and are not performed by a repository commit.
