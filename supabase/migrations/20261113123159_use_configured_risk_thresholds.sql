create or replace function public.analytics_period_summary(
  p_start timestamptz,
  p_end timestamptz,
  p_interval text default 'day',
  p_dimension text default 'none'
) returns jsonb
language plpgsql
stable
security invoker
set search_path = public
as $$
declare result jsonb;
begin
  if p_end <= p_start then raise exception 'p_end must be later than p_start'; end if;
  if p_interval not in ('day','week','month') then raise exception 'Unsupported aggregation interval'; end if;
  if p_dimension not in ('none','category','channel','account_tier','behavior_segment') then raise exception 'Unsupported analytics dimension'; end if;
  with current_tx as (
    select t.*, c.account_tier, coalesce(f.behavior_segment,'unclassified') as behavior_segment,
      date_trunc(p_interval,t."timestamp") as bucket
    from public.transactions t
    join public.customers c on c.customer_id=t.customer_id
    left join public.customer_features f on f.customer_id=t.customer_id
    where t."timestamp">=p_start and t."timestamp"<p_end
  ), previous_tx as (
    select * from public.transactions
    where "timestamp">=(p_start-(p_end-p_start)) and "timestamp"<p_start
  ), trend as (
    select bucket,count(*)::bigint as transaction_count,
      coalesce(sum(amount) filter(where transaction_type='Debit'),0) as debit_volume,
      coalesce(sum(amount) filter(where transaction_type='Credit'),0) as credit_volume
    from current_tx group by bucket order by bucket
  ), category_rows as (
    select merchant_category as name,count(*)::bigint as transaction_count,coalesce(sum(amount),0) as volume
    from current_tx group by merchant_category order by volume desc
  ), channel_rows as (
    select channel as name,count(*)::bigint as transaction_count,coalesce(sum(amount),0) as volume
    from current_tx group by channel order by transaction_count desc
  ), dimension_rows as (
    select case p_dimension
      when 'category' then merchant_category when 'channel' then channel
      when 'account_tier' then account_tier when 'behavior_segment' then behavior_segment else 'all'
    end as name,count(*)::bigint as transaction_count,coalesce(sum(amount),0) as volume
    from current_tx group by 1 order by volume desc
  ), metrics as (
    select count(*)::bigint as transaction_count,
      coalesce(sum(amount) filter(where transaction_type='Debit'),0) as debit_volume,
      coalesce(sum(amount) filter(where transaction_type='Credit'),0) as credit_volume,
      coalesce(avg(amount),0) as average_transaction_value
    from current_tx
  ), previous_metrics as (
    select count(*)::bigint as transaction_count,
      coalesce(sum(amount) filter(where transaction_type='Debit'),0) as debit_volume,
      coalesce(sum(amount) filter(where transaction_type='Credit'),0) as credit_volume
    from previous_tx
  ), risk as (
    select count(*)::bigint as assessed,
      count(*) filter(where i.churn_risk_score<=t.low_max)::bigint as low,
      count(*) filter(where i.churn_risk_score>t.low_max and i.churn_risk_score<=t.moderate_max)::bigint as moderate,
      count(*) filter(where i.churn_risk_score>t.moderate_max)::bigint as high,
      coalesce(avg(i.churn_risk_score),0) as average_score
    from public.predictive_insights i
    cross join public.risk_thresholds t
    where t.name='default' and t.is_active=true
  )
  select jsonb_build_object(
    'period_start',p_start,'period_end',p_end,'aggregation_interval',p_interval,'dimension',p_dimension,'generated_at',now(),
    'metrics',(select to_jsonb(metrics)||jsonb_build_object(
      'net_flow',metrics.credit_volume-metrics.debit_volume,
      'previous_transaction_count',previous_metrics.transaction_count,
      'previous_debit_volume',previous_metrics.debit_volume,'previous_credit_volume',previous_metrics.credit_volume,
      'transaction_count_change_pct',case when previous_metrics.transaction_count=0 then null else round((metrics.transaction_count-previous_metrics.transaction_count)*100.0/previous_metrics.transaction_count,2) end,
      'debit_volume_change_pct',case when previous_metrics.debit_volume=0 then null else round((metrics.debit_volume-previous_metrics.debit_volume)*100.0/previous_metrics.debit_volume,2) end,
      'credit_volume_change_pct',case when previous_metrics.credit_volume=0 then null else round((metrics.credit_volume-previous_metrics.credit_volume)*100.0/previous_metrics.credit_volume,2) end
    ) from metrics cross join previous_metrics),
    'transaction_trend',coalesce((select jsonb_agg(jsonb_build_object('bucket',bucket,'transaction_count',transaction_count,'debit_volume',debit_volume,'credit_volume',credit_volume) order by bucket) from trend),'[]'::jsonb),
    'category_breakdown',coalesce((select jsonb_agg(to_jsonb(category_rows)) from category_rows),'[]'::jsonb),
    'channel_breakdown',coalesce((select jsonb_agg(to_jsonb(channel_rows)) from channel_rows),'[]'::jsonb),
    'dimension_breakdown',coalesce((select jsonb_agg(to_jsonb(dimension_rows)) from dimension_rows),'[]'::jsonb),
    'risk_metrics',(select to_jsonb(risk) from risk)
  ) into result;
  return result;
end;
$$;
revoke all on function public.analytics_period_summary(timestamptz,timestamptz,text,text) from public,anon,authenticated;
grant execute on function public.analytics_period_summary(timestamptz,timestamptz,text,text) to service_role;
