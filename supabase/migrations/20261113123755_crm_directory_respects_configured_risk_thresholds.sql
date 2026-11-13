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
  select c.customer_id,c.full_name,c.email,c.account_tier,c.created_at,
         f.recency_days,f.frequency_30d,f.monetary_spend_90d,f.balance_avg_30d,
         f.velocity_score,f.discretionary_spend_ratio,f.salary_disruption_flag,
         f.balance_drawdown_pct,f.behavior_segment,
         i.churn_risk_score,i.primary_churn_driver,i.recommended_product,
         i.prescriptive_action,i.evaluated_at,
         case when coalesce(i.churn_risk_score,0)>rt.moderate_max then 'high'
              when coalesce(i.churn_risk_score,0)>rt.low_max then 'moderate'
              else 'low' end as risk_band
  from public.customers c
  cross join public.risk_thresholds rt
  left join public.customer_features f on f.customer_id=c.customer_id
  left join public.predictive_insights i on i.customer_id=c.customer_id
  where rt.name='default' and rt.is_active=true
    and (p_search is null or btrim(p_search)='' or
      c.full_name ilike '%'||btrim(p_search)||'%' or
      c.email ilike '%'||btrim(p_search)||'%' or
      c.customer_id::text ilike '%'||btrim(p_search)||'%')
    and (p_account_tier is null or c.account_tier=p_account_tier)
    and (p_risk_band is null or
      case when coalesce(i.churn_risk_score,0)>rt.moderate_max then 'high'
           when coalesce(i.churn_risk_score,0)>rt.low_max then 'moderate'
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
  'customers',coalesce((select jsonb_agg(to_jsonb(page_rows)) from page_rows),'[]'::jsonb),
  'total',(select count(*) from filtered),
  'page',greatest(p_page,1),
  'page_size',least(greatest(p_page_size,1),100)
);
$$;
revoke all on function public.crm_customer_directory(text,text,text,text,date,date,text,text,integer,integer) from public,anon,authenticated;
grant execute on function public.crm_customer_directory(text,text,text,text,date,date,text,text,integer,integer) to service_role;
