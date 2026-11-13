-- Samora Ledger Tech: additive enterprise CRM, risk, reporting and governance foundation
-- Safe for the populated MVP schema: no existing table is dropped or truncated.
create extension if not exists pgcrypto;

create table if not exists public.staff_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  email text,
  role text not null check (role in ('executive','analyst','relationship_manager','admin')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.customer_feature_history (
  feature_snapshot_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  calculated_at timestamptz not null default now(),
  feature_engine_version text not null,
  recency_days integer,
  frequency_30d integer,
  monetary_spend_30d numeric(18,2),
  monetary_spend_60d numeric(18,2),
  monetary_spend_90d numeric(18,2),
  average_transaction_value_90d numeric(18,2),
  balance_avg_30d numeric(18,2),
  balance_drawdown_pct numeric(8,5),
  velocity_score numeric(12,4),
  discretionary_spend_ratio numeric(8,5),
  salary_disruption_flag boolean,
  behavior_segment text,
  unique(customer_id, calculated_at, feature_engine_version)
);
create index if not exists idx_feature_history_customer_time on public.customer_feature_history(customer_id, calculated_at desc);

create table if not exists public.crm_interactions (
  interaction_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  staff_user_id uuid not null references auth.users(id),
  interaction_type text not null check (interaction_type in ('call','email','meeting','branch_visit','message','other')),
  subject text not null,
  notes text,
  outcome text,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index if not exists idx_crm_interactions_customer_time on public.crm_interactions(customer_id, occurred_at desc);

create table if not exists public.crm_tasks (
  task_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  title text not null,
  description text,
  priority text not null default 'medium' check (priority in ('low','medium','high','urgent')),
  status text not null default 'open' check (status in ('open','in_progress','completed','cancelled')),
  assigned_to uuid references auth.users(id),
  created_by uuid not null references auth.users(id),
  due_at timestamptz,
  completed_at timestamptz,
  outcome text,
  idempotency_key text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((status <> 'completed') or completed_at is not null)
);
create index if not exists idx_crm_tasks_status_due on public.crm_tasks(status, due_at);
create index if not exists idx_crm_tasks_customer on public.crm_tasks(customer_id, created_at desc);
create index if not exists idx_crm_tasks_assignee on public.crm_tasks(assigned_to, status);

create table if not exists public.crm_task_history (
  history_id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.crm_tasks(task_id) on delete cascade,
  actor_user_id uuid not null references auth.users(id),
  event_type text not null,
  old_values jsonb,
  new_values jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_crm_task_history_task_time on public.crm_task_history(task_id, created_at desc);

create table if not exists public.risk_thresholds (
  threshold_id uuid primary key default gen_random_uuid(),
  name text not null unique,
  low_max numeric(5,2) not null default 29.99,
  moderate_max numeric(5,2) not null default 59.99,
  significant_movement numeric(5,2) not null default 15,
  is_active boolean not null default true,
  configured_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (low_max >= 0 and moderate_max > low_max and moderate_max < 100),
  check (significant_movement > 0 and significant_movement <= 100)
);
insert into public.risk_thresholds(name) values ('default') on conflict (name) do nothing;

create table if not exists public.risk_score_history (
  risk_history_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  risk_score numeric(5,2) not null check (risk_score between 0 and 100),
  risk_band text not null check (risk_band in ('low','moderate','high')),
  primary_risk_driver text,
  rules_engine_version text not null,
  model_run_id uuid,
  assessed_at timestamptz not null default now(),
  unique(customer_id, assessed_at, rules_engine_version)
);
create index if not exists idx_risk_history_customer_time on public.risk_score_history(customer_id, assessed_at desc);
create index if not exists idx_risk_history_band_time on public.risk_score_history(risk_band, assessed_at desc);

create table if not exists public.risk_alerts (
  alert_id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(customer_id) on delete cascade,
  risk_history_id uuid references public.risk_score_history(risk_history_id) on delete set null,
  alert_type text not null check (alert_type in ('band_increased','significant_increase','threshold_breached')),
  previous_score numeric(5,2),
  current_score numeric(5,2) not null,
  status text not null default 'open' check (status in ('open','acknowledged','resolved')),
  acknowledged_by uuid references auth.users(id),
  acknowledged_at timestamptz,
  resolution_note text,
  resolved_by uuid references auth.users(id),
  resolved_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists idx_risk_alerts_status_time on public.risk_alerts(status, created_at desc);
create index if not exists idx_risk_alerts_customer_time on public.risk_alerts(customer_id, created_at desc);

create table if not exists public.executive_analytics_snapshots (
  snapshot_id uuid primary key default gen_random_uuid(),
  period_start date not null,
  period_end date not null,
  aggregation_interval text not null check (aggregation_interval in ('day','week','month')),
  dimension text not null default 'none',
  metrics jsonb not null,
  model_version text,
  data_cutoff_at timestamptz not null,
  generated_at timestamptz not null default now(),
  scheduled_run_key text unique,
  created_by uuid references auth.users(id),
  check (period_end >= period_start)
);
create index if not exists idx_exec_snapshots_period on public.executive_analytics_snapshots(period_start, period_end desc);

create table if not exists public.report_definitions (
  report_definition_id uuid primary key default gen_random_uuid(),
  report_key text not null unique,
  name text not null,
  description text,
  configuration jsonb not null default '{}'::jsonb,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table if not exists public.report_runs (
  report_id uuid primary key default gen_random_uuid(),
  report_definition_id uuid references public.report_definitions(report_definition_id) on delete set null,
  report_key text not null,
  requested_by uuid not null references auth.users(id),
  period_start date not null,
  period_end date not null,
  status text not null default 'completed' check (status in ('queued','running','completed','failed')),
  analytics_version text not null,
  data_cutoff_at timestamptz not null,
  generated_at timestamptz not null default now(),
  error_summary text,
  parameters jsonb not null default '{}'::jsonb,
  check (period_end >= period_start)
);
create index if not exists idx_report_runs_generated on public.report_runs(generated_at desc);
create table if not exists public.report_snapshots (
  report_snapshot_id uuid primary key default gen_random_uuid(),
  report_id uuid not null references public.report_runs(report_id) on delete cascade,
  section_key text not null,
  content jsonb not null,
  created_at timestamptz not null default now(),
  unique(report_id, section_key)
);

create table if not exists public.model_versions (
  model_version_id uuid primary key default gen_random_uuid(),
  version text not null unique,
  model_type text not null check (model_type in ('rules_engine','statistical_model','machine_learning')),
  description text,
  is_active boolean not null default false,
  created_at timestamptz not null default now()
);
insert into public.model_versions(version,model_type,description,is_active)
values ('rules-v1','rules_engine','Transparent heuristic churn-risk baseline; not a validated predictive model.',true)
on conflict (version) do nothing;
create table if not exists public.model_runs (
  model_run_id uuid primary key default gen_random_uuid(),
  model_version_id uuid references public.model_versions(model_version_id),
  status text not null check (status in ('running','completed','failed','partial')),
  customers_evaluated integer not null default 0,
  records_skipped integer not null default 0,
  records_failed integer not null default 0,
  execution_duration_ms bigint,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  initiated_by uuid references auth.users(id),
  metrics jsonb,
  error_summary text
);
create index if not exists idx_model_runs_started on public.model_runs(started_at desc);
create table if not exists public.model_configurations (
  configuration_id uuid primary key default gen_random_uuid(),
  configuration_key text not null,
  configuration_value jsonb not null,
  version integer not null default 1,
  changed_by uuid references auth.users(id),
  created_at timestamptz not null default now(),
  unique(configuration_key, version)
);
create table if not exists public.model_audit_logs (
  audit_id uuid primary key default gen_random_uuid(),
  actor_user_id uuid references auth.users(id),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  before_state jsonb,
  after_state jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_model_audit_time on public.model_audit_logs(created_at desc);

create table if not exists public.organisations (
  organisation_id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);
create table if not exists public.organisation_settings (
  setting_id uuid primary key default gen_random_uuid(),
  organisation_id uuid not null references public.organisations(organisation_id) on delete cascade,
  setting_key text not null,
  setting_value jsonb not null,
  updated_by uuid references auth.users(id),
  updated_at timestamptz not null default now(),
  unique(organisation_id, setting_key)
);
create table if not exists public.user_preferences (
  user_id uuid not null references auth.users(id) on delete cascade,
  preference_key text not null,
  preference_value jsonb not null,
  updated_at timestamptz not null default now(),
  primary key(user_id, preference_key)
);

-- All new enterprise tables are private to the trusted API. The API verifies
-- Supabase JWT identity and role before using its server-side service-role client.
do $$
declare t text;
begin
  foreach t in array array[
    'staff_profiles','customer_feature_history','crm_interactions','crm_tasks','crm_task_history',
    'risk_thresholds','risk_score_history','risk_alerts','executive_analytics_snapshots',
    'report_definitions','report_runs','report_snapshots','model_versions','model_runs',
    'model_configurations','model_audit_logs','organisations','organisation_settings','user_preferences'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
    execute format('grant all on public.%I to service_role', t);
  end loop;
end $$;

-- Staff can read their own profile only. All administrative writes go through
-- the authenticated and role-checked backend API.
grant select on public.staff_profiles to authenticated;
drop policy if exists staff_read_own_profile on public.staff_profiles;
create policy staff_read_own_profile on public.staff_profiles
  for select to authenticated using (user_id = (select auth.uid()));


-- Indexed, server-side CRM directory query. The function is callable only by service_role;
-- application code authenticates the staff JWT and checks role before invoking it.
create or replace function public.crm_customer_directory(
  p_search text default null,
  p_account_tier text default null,
  p_risk_band text default null,
  p_segment text default null,
  p_created_from date default null,
  p_created_to date default null,
  p_sort_by text default 'name',
  p_sort_dir text default 'asc',
  p_page integer default 1,
  p_page_size integer default 25
) returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
with filtered as (
  select c.customer_id, c.full_name, c.email, c.account_tier, c.created_at,
         f.recency_days, f.frequency_30d, f.monetary_spend_90d, f.balance_avg_30d,
         f.velocity_score, f.discretionary_spend_ratio, f.salary_disruption_flag,
         f.balance_drawdown_pct, f.behavior_segment,
         i.churn_risk_score, i.primary_churn_driver, i.recommended_product,
         i.prescriptive_action, i.evaluated_at,
         case when coalesce(i.churn_risk_score,0) >= 60 then 'high'
              when coalesce(i.churn_risk_score,0) >= 30 then 'moderate'
              else 'low' end as risk_band
  from public.customers c
  left join public.customer_features f on f.customer_id=c.customer_id
  left join public.predictive_insights i on i.customer_id=c.customer_id
  where
    (p_search is null or btrim(p_search)='' or
      c.full_name ilike '%'||btrim(p_search)||'%' or
      c.email ilike '%'||btrim(p_search)||'%' or
      c.customer_id::text ilike '%'||btrim(p_search)||'%')
    and (p_account_tier is null or c.account_tier=p_account_tier)
    and (p_risk_band is null or
      case when coalesce(i.churn_risk_score,0)>=60 then 'high'
           when coalesce(i.churn_risk_score,0)>=30 then 'moderate'
           else 'low' end=p_risk_band)
    and (p_segment is null or f.behavior_segment=p_segment)
    and (p_created_from is null or c.created_at::date>=p_created_from)
    and (p_created_to is null or c.created_at::date<=p_created_to)
), ordered as (
  select * from filtered
  order by
    case when p_sort_by='name' and lower(p_sort_dir)='asc' then full_name end asc,
    case when p_sort_by='name' and lower(p_sort_dir)='desc' then full_name end desc,
    case when p_sort_by='risk_score' and lower(p_sort_dir)='asc' then churn_risk_score end asc nulls last,
    case when p_sort_by='risk_score' and lower(p_sort_dir)='desc' then churn_risk_score end desc nulls last,
    case when p_sort_by='account_tier' and lower(p_sort_dir)='asc' then account_tier end asc,
    case when p_sort_by='account_tier' and lower(p_sort_dir)='desc' then account_tier end desc,
    case when p_sort_by='created_at' and lower(p_sort_dir)='asc' then created_at end asc,
    case when p_sort_by='created_at' and lower(p_sort_dir)='desc' then created_at end desc,
    customer_id
), page_rows as (
  select * from ordered
  offset ((greatest(p_page,1)-1)*least(greatest(p_page_size,1),100))
  limit least(greatest(p_page_size,1),100)
)
select jsonb_build_object(
  'customers', coalesce((select jsonb_agg(to_jsonb(page_rows)) from page_rows),'[]'::jsonb),
  'total', (select count(*) from filtered),
  'page', greatest(p_page,1),
  'page_size', least(greatest(p_page_size,1),100)
);
$$;
revoke all on function public.crm_customer_directory(text,text,text,text,date,date,text,text,integer,integer) from public, anon, authenticated;
grant execute on function public.crm_customer_directory(text,text,text,text,date,date,text,text,integer,integer) to service_role;
