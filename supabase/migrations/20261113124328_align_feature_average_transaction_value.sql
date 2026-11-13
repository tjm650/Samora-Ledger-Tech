with averages as (
  select fh.feature_snapshot_id,
    coalesce(avg(t.amount),0)::numeric(18,2) as average_transaction_value_90d
  from public.customer_feature_history fh
  left join public.transactions t
    on t.customer_id=fh.customer_id
   and t."timestamp">=fh.calculated_at-interval '90 days'
   and t."timestamp"<=fh.calculated_at
  group by fh.feature_snapshot_id
)
update public.customer_feature_history fh
set average_transaction_value_90d=averages.average_transaction_value_90d
from averages
where averages.feature_snapshot_id=fh.feature_snapshot_id;
