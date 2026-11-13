# Samora Ledger Tech
Enterprise Banking Transaction Analytics & Executive Decision-Support MVP.

## Source layout
- `database/schema.sql` — original Supabase core schema.
- `supabase/migrations/` — additive, version-controlled enterprise schema migrations.
- `backend/` — Python 3.11 FastAPI service, feature engineering, transparent churn scoring, CRM workflow, risk monitoring, management reports, governance and settings APIs.
- `frontend/` — Next.js App Router executive workspace: overview, transactions, risk, analytics, reports, governance, CRM, customer profiles and settings.
- `render.yaml` — Render deployment blueprint.

## Existing data and safe migrations
The original populated tables remain intact: `customers`, `transactions`, `customer_features` and `predictive_insights`. Enterprise functionality is added through non-destructive migrations; no existing customer or transaction rows are recreated.

Migrations currently include:
- `20261113130000_enterprise_crm_risk_reporting_governance.sql`
- `20261113140000_harden_enterprise_rls_and_indexes.sql`
- `20261113150000_use_configured_risk_thresholds.sql`
- `20261113160000_version_scoring_configuration_references.sql`
- `20261113170000_crm_search_indexes_and_updated_at.sql`
- `20261113180000_relocate_trigram_extension_and_deduplicate_index.sql`

The migrations have been applied to the configured Supabase project and verified in its migration history. For a new environment, apply the migrations in timestamp order after the original core schema.

## Local setup
1. Create a Supabase project and apply `database/schema.sql`, followed by the timestamped migrations in `supabase/migrations/`.
2. Copy `backend/.env.example` to `backend/.env`, set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `API_KEY`. Never expose the service-role key to the browser.
3. From `backend`: `python -m venv .venv && pip install -r requirements.txt`; start the API with `uvicorn main:app --reload`.
4. Copy `frontend/.env.example` to `frontend/.env.local`. Set server-side `SAMORA_API_URL` and `SAMORA_API_KEY`, plus `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Run `npm install && npm run dev` from `frontend`.
5. Configure Render with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `API_KEY`, and `API_CORS_ORIGINS`. Configure Vercel with the two server-side Samora variables and the two public Supabase Auth variables. Do not prefix server secrets with `NEXT_PUBLIC_`.
6. Provision staff accounts through the trusted Supabase Auth administration process. Assign approved `app_metadata.role` values: `executive`, `admin`, `analyst`, or `relationship_manager`. The frontend has no public registration. Never grant roles through user-editable metadata.

## API surface
All staff-facing data and management APIs require the private `X-API-Key` header and a verified Supabase staff JWT in `Authorization: Bearer <token>`. The health endpoint is public. Pipeline and one-shot demo administration operations are restricted to the trusted server-side proxy/API key and are never exposed to browser clients.

- `GET /health`
- `GET /api/v1/executive/overview`
- `GET /api/v1/executive/transactions`
- `GET /api/v1/analytics/overview` — custom date range, daily/weekly/monthly aggregation, previous-period comparison, category/channel/account-tier/behaviour-segment dimensions.
- `GET /api/v1/analytics/snapshots`
- `GET /api/v1/crm/customers` — search, filters, sorting and pagination.
- `GET /api/v1/crm/customers/{customer_id}` — consolidated profile and spending metrics.
- `GET|POST /api/v1/crm/customers/{customer_id}/interactions`
- `GET|POST /api/v1/crm/tasks`, `PATCH /api/v1/crm/tasks/{task_id}`
- `GET /api/v1/crm/customers/{customer_id}/tasks`
- `GET /api/v1/risk/summary`, `/trends`, `/alerts`, `/thresholds`
- `GET /api/v1/reports`, `POST /api/v1/reports/generate`, `GET /api/v1/reports/{report_id}`, `GET /api/v1/reports/{report_id}/download?format=csv`
- `GET /api/v1/governance/models`, `/runs`, `/configuration`, `/audit-logs`
- `GET /api/v1/settings/me`, `/preferences`, `/organisation`

The legacy `GET /api/v1/customers` and `GET /api/v1/explain/{customer_id}` routes remain as authenticated compatibility endpoints.

## Security and roles
The Next.js workspace requires Supabase Auth sessions and trusted `app_metadata.role` claims. Backend routes independently validate the staff JWT and role before using the server-side service-role database client. New enterprise tables have RLS enabled, are not granted to anon/authenticated Data API roles, and have explicit service-role policies. The staff profile table permits authenticated users to read only their own profile.

The CRM directory and customer profiles are confidential staff functionality. Executive aggregate analytics omit customer-level information. The Supabase service-role key and Render API key are server-only.

## Model and data limitations
The MVP uses a transparent rules-based churn-risk baseline, not a trained production classifier. It is not credit risk or probability of default. Explanations are not SHAP. No model accuracy, precision, recall or AUC is reported because there is no labelled churn-outcome dataset. Feature/risk history and model run records are written on future pipeline runs; no historical records are fabricated retroactively.

The existing demo dataset is synthetic. Product offers are not validated suitability decisions. Currency values are not FX-normalised. Branch and geographic analytics are not exposed because those source dimensions do not exist. CSV management report export is supported; PDF export is not yet implemented.

## Validation
CI compiles the Python backend, runs backend tests and runs the frontend TypeScript type-check. Live Render/Vercel deployment verification is tracked separately from source commits. The demo seeder is one-shot and must only be used against an empty disposable demo database.
