create or replace function public.risk_score_movements(
  p_since timestamptz default now()-interval '90 days',
  p_direction text default 'all'
) returns jsonb
language sql
stable
security invoker
set search_path = public
as $$
with ranked as (
  select customer_id,risk_score,risk_band,assessed_at,
    row_number() over(partition by customer_id order by assessed_at desc) as rn
  from public.risk_score_history
), movements as (
  select current.customer_id,
    previous.risk_score as previous_score,
    current.risk_score as current_score,
    previous.risk_band as previous_band,
    current.risk_band as current_band,
    round(current.risk_score-previous.risk_score,2) as score_change,
    current.assessed_at
  from ranked current
  join ranked previous on previous.customer_id=current.customer_id and previous.rn=2
  where current.rn=1 and current.assessed_at>=p_since
)
select jsonb_build_object(
  'total',count(*),
  'movements',coalesce(jsonb_agg(to_jsonb(movements) order by abs(score_change) desc),'[]'::jsonb)
)
from movements
where p_direction='all'
   or (p_direction='increased' and score_change>0)
   or (p_direction='decreased' and score_change<0);
$$;
revoke all on function public.risk_score_movements(timestamptz,text) from public,anon,authenticated;
grant execute on function public.risk_score_movements(timestamptz,text) to service_role;
