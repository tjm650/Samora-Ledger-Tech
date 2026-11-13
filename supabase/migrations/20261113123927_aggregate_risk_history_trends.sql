create or replace function public.risk_history_trend(
  p_since timestamptz,
  p_interval text default 'day'
) returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
  select coalesce(jsonb_agg(jsonb_build_object(
    'bucket',bucket,
    'average_score',average_score,
    'low',low_count,
    'moderate',moderate_count,
    'high',high_count,
    'customers_assessed',customers_assessed
  ) order by bucket),'[]'::jsonb)
  from (
    select date_trunc(p_interval,assessed_at) as bucket,
      round(avg(risk_score),2) as average_score,
      count(*) filter(where risk_band='low')::bigint as low_count,
      count(*) filter(where risk_band='moderate')::bigint as moderate_count,
      count(*) filter(where risk_band='high')::bigint as high_count,
      count(distinct customer_id)::bigint as customers_assessed
    from public.risk_score_history
    where assessed_at>=p_since
    group by date_trunc(p_interval,assessed_at)
  ) grouped;
$$;
revoke all on function public.risk_history_trend(timestamptz,text) from public,anon,authenticated;
grant execute on function public.risk_history_trend(timestamptz,text) to service_role;
