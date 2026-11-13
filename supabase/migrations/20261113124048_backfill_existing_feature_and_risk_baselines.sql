-- Establish one truthful baseline snapshot per customer from existing persisted
-- features/assessments and transaction history. This does not infer prior risk movement.
with feature_rows as (
  select f.customer_id,
    f.updated_at as calculated_at,
    'features-v1'::text as feature_engine_version,
    f.recency_days,
    f.frequency_30d,
    coalesce(sum(t.amount) filter (
      where t.transaction_type='Debit' and t."timestamp">=f.updated_at-interval '30 days'
    ),0)::numeric(18,2) as monetary_spend_30d,
    coalesce(sum(t.amount) filter (
      where t.transaction_type='Debit' and t."timestamp">=f.updated_at-interval '60 days'
    ),0)::numeric(18,2) as monetary_spend_60d,
    coalesce(sum(t.amount) filter (
      where t.transaction_type='Debit'
    ),0)::numeric(18,2) as monetary_spend_90d,
    coalesce(avg(t.amount) filter (
      where t.transaction_type='Debit'
    ),0)::numeric(18,2) as average_transaction_value_90d,
    f.balance_avg_30d,
    f.balance_drawdown_pct,
    f.velocity_score,
    f.discretionary_spend_ratio,
    f.salary_disruption_flag,
    f.behavior_segment
  from public.customer_features f
  left join public.transactions t
    on t.customer_id=f.customer_id
   and t."timestamp">=f.updated_at-interval '90 days'
   and t."timestamp"<=f.updated_at
  group by f.customer_id,f.updated_at,f.recency_days,f.frequency_30d,
    f.balance_avg_30d,f.balance_drawdown_pct,f.velocity_score,
    f.discretionary_spend_ratio,f.salary_disruption_flag,f.behavior_segment
)
insert into public.customer_feature_history(
  customer_id,calculated_at,feature_engine_version,recency_days,frequency_30d,
  monetary_spend_30d,monetary_spend_60d,monetary_spend_90d,
  average_transaction_value_90d,balance_avg_30d,balance_drawdown_pct,
  velocity_score,discretionary_spend_ratio,salary_disruption_flag,behavior_segment
)
select customer_id,calculated_at,feature_engine_version,recency_days,frequency_30d,
  monetary_spend_30d,monetary_spend_60d,monetary_spend_90d,
  average_transaction_value_90d,balance_avg_30d,balance_drawdown_pct,
  velocity_score,discretionary_spend_ratio,salary_disruption_flag,behavior_segment
from feature_rows
on conflict (customer_id,calculated_at,feature_engine_version) do nothing;

insert into public.risk_score_history(
  customer_id,risk_score,risk_band,primary_risk_driver,
  rules_engine_version,configuration_version,assessed_at
)
select i.customer_id,i.churn_risk_score,
  case when i.churn_risk_score>t.moderate_max then 'high'
       when i.churn_risk_score>t.low_max then 'moderate'
       else 'low' end,
  i.primary_churn_driver,'rules-v1',
  (select max(mc.version) from public.model_configurations mc where mc.configuration_key='rules-v1-scoring-baseline'),
  i.evaluated_at
from public.predictive_insights i
cross join public.risk_thresholds t
where t.name='default' and t.is_active=true
on conflict (customer_id,assessed_at,rules_engine_version) do nothing;
