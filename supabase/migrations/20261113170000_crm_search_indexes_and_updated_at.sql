create extension if not exists pg_trgm;

create index if not exists idx_customers_account_tier on public.customers(account_tier);
create index if not exists idx_customers_created_at on public.customers(created_at desc);
create index if not exists idx_customers_name_trgm on public.customers using gin(full_name gin_trgm_ops);
create index if not exists idx_customers_email_trgm on public.customers using gin(email gin_trgm_ops);
create index if not exists idx_customer_features_segment on public.customer_features(behavior_segment);
create index if not exists idx_predictive_insights_risk_score on public.predictive_insights(churn_risk_score desc);

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke all on function private.set_updated_at() from public, anon, authenticated;

do $$
declare t text;
begin
  foreach t in array array[
    'staff_profiles','crm_tasks','risk_thresholds','report_definitions',
    'organisation_settings','user_preferences'
  ] loop
    execute format('drop trigger if exists set_updated_at on public.%I',t);
    execute format('create trigger set_updated_at before update on public.%I for each row execute function private.set_updated_at()',t);
  end loop;
end $$;
