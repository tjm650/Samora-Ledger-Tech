create schema if not exists extensions;
alter extension pg_trgm set schema extensions;
drop index if exists public.idx_predictive_insights_risk_score;
