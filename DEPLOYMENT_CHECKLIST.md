# Deployment checklist

## Supabase
- Create a dedicated demo/staging project and apply `database/schema.sql`.
- Confirm RLS is enabled and validate policies using customer and staff test identities.
- Keep the service-role key only in Render secrets; rotate if exposed.
- Seed only disposable demo data after setting `ALLOW_DEMO_SEEDING=true`.

## Render
- Create a Blueprint from repository root (uses `render.yaml`).
- Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `API_KEY`, and exact Vercel origin(s) in environment settings.
- Confirm `/health` returns HTTP 200.
- Trigger pipeline using `X-API-Key`; inspect logs and verify feature/insight upserts.

## Vercel
- Import repository and set Root Directory to `frontend`.
- Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- Deploy and verify overview, CRM, CSV export, and customer detail under authenticated Supabase roles.

## Production readiness gates
- Replace demo proxy/rule scores with outcome-labelled, temporally validated models.
- Add robust staff authentication and authorization for operational actions; review RLS with a security specialist.
- Add pagination, query batching, rate limiting, audit logging, monitoring, backup/restore tests and incident response.
- Complete privacy, model-risk, fairness, suitability, regulatory and penetration testing.
