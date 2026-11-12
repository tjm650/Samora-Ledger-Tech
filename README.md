# Samora Ledger Tech
Enterprise Banking Transaction Analytics & Action Engine MVP.

## Source layout
- `database/schema.sql` — Supabase PostgreSQL tables, constraints, indexes and RLS.
- `backend/` — Python 3.11 FastAPI service, synthetic data seeder and analytics pipeline.
- `frontend/` — Next.js App Router dashboard, operational CRM and customer detail view.
- `render.yaml` — Render deployment blueprint.
- `.github/workflows/ci.yml` — backend tests and frontend type-check workflow.

## Local setup
1. Create a disposable Supabase project and apply `database/schema.sql` in the SQL editor.
2. Copy `backend/.env.example` to `backend/.env`, set the project URL and service-role key. Never expose the service-role key to the browser.
3. From `backend`: `python -m venv .venv && pip install -r requirements.txt`; run `ALLOW_DEMO_SEEDING=true python data_seeder.py` only on a disposable demo database; start API with `uvicorn main:app --reload`.
4. Copy `frontend/.env.example` to `frontend/.env.local`, set `SAMORA_API_URL` to the Render service base URL and `SAMORA_API_KEY` to the Render `API_KEY` value, then from `frontend`: `npm install && npm run dev`. Keep both variables server-side (never prefix them with `NEXT_PUBLIC_`). The optional Supabase anon variables are only needed for separately approved browser-side Supabase features.
5. Configure `API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and allowed CORS origins in Render. In Vercel, set root directory to `frontend` and configure server-side `SAMORA_API_URL` and `SAMORA_API_KEY` with the Render service URL and Render `API_KEY` value. Never expose either key in browser variables.

## API
- `GET /health`
- `POST /api/v1/run-pipeline` with `X-API-Key`
- `GET /api/v1/explain/{customer_id}` with `X-API-Key`

## Important model and security limitations
This MVP uses transparent rule-based risk scoring rather than a trained production classifier. It does not estimate revenue-at-risk because account margin/revenue data is not part of the requested schema. Explanations are not SHAP values. Synthetic cohort patterns are not validated churn labels. Before real use, replace the scoring baseline with outcome-labelled temporal model training, calibration, independent validation, fairness and drift testing, governance, access review and human oversight. Product offers require suitability, eligibility and consent controls. Restrict portfolio roles through trusted Supabase `app_metadata`; never grant those roles from user-editable metadata. Seeder is demo-only and must never run against production customer data.

## Validation
CI installs backend dependencies and compiles the Python service; frontend CI runs TypeScript type-check. Live Supabase, Render and Vercel deployment require your project credentials and are not performed by a repository commit.
