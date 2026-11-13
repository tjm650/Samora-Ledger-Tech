alter table public.model_runs
  add column if not exists configuration_version integer;
alter table public.risk_score_history
  add column if not exists configuration_version integer;
alter table public.report_runs
  add column if not exists configuration_version integer;
