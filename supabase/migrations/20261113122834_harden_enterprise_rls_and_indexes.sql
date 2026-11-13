-- Explicit service-role RLS policies and foreign-key indexes for enterprise tables.
do $$
declare t text;
begin
  foreach t in array array[
    'staff_profiles','customer_feature_history','crm_interactions','crm_tasks','crm_task_history',
    'risk_thresholds','risk_score_history','risk_alerts','executive_analytics_snapshots',
    'report_definitions','report_runs','report_snapshots','model_versions','model_runs',
    'model_configurations','model_audit_logs','organisations','organisation_settings','user_preferences'
  ] loop
    if not exists (
      select 1 from pg_policies
      where schemaname='public' and tablename=t and policyname='service_role_all'
    ) then
      execute format('create policy service_role_all on public.%I for all to service_role using (true) with check (true)',t);
    end if;
  end loop;
end $$;

create index if not exists idx_crm_interactions_staff on public.crm_interactions(staff_user_id);
create index if not exists idx_crm_task_history_actor on public.crm_task_history(actor_user_id);
create index if not exists idx_crm_tasks_creator on public.crm_tasks(created_by);
create index if not exists idx_exec_snapshots_creator on public.executive_analytics_snapshots(created_by);
create index if not exists idx_model_audit_actor on public.model_audit_logs(actor_user_id);
create index if not exists idx_model_config_changed_by on public.model_configurations(changed_by);
create index if not exists idx_model_runs_version on public.model_runs(model_version_id);
create index if not exists idx_model_runs_initiator on public.model_runs(initiated_by);
create index if not exists idx_org_settings_updated_by on public.organisation_settings(updated_by);
create index if not exists idx_report_runs_definition on public.report_runs(report_definition_id);
create index if not exists idx_report_runs_requester on public.report_runs(requested_by);
create index if not exists idx_risk_alerts_acknowledged_by on public.risk_alerts(acknowledged_by);
create index if not exists idx_risk_alerts_resolved_by on public.risk_alerts(resolved_by);
create index if not exists idx_risk_alerts_history_id on public.risk_alerts(risk_history_id);
create index if not exists idx_risk_history_model_run on public.risk_score_history(model_run_id);
create index if not exists idx_risk_thresholds_configured_by on public.risk_thresholds(configured_by);
