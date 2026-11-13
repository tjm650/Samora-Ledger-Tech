-- Keep JWT helper calls initPlan-stable rather than re-evaluating per row.
drop policy if exists customer_self_read on public.customers;
create policy customer_self_read on public.customers for select to authenticated using (
  auth_user_id = (select auth.uid()) or
  ((select auth.jwt())->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')
);
drop policy if exists customer_self_update on public.customers;
create policy customer_self_update on public.customers for update to authenticated using (
  auth_user_id = (select auth.uid())
) with check (
  auth_user_id = (select auth.uid())
);
drop policy if exists transaction_portfolio_read on public.transactions;
create policy transaction_portfolio_read on public.transactions for select to authenticated using (
  exists(select 1 from public.customers c where c.customer_id=transactions.customer_id and
    (c.auth_user_id=(select auth.uid()) or
     ((select auth.jwt())->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')))
);
drop policy if exists feature_portfolio_read on public.customer_features;
create policy feature_portfolio_read on public.customer_features for select to authenticated using (
  exists(select 1 from public.customers c where c.customer_id=customer_features.customer_id and
    (c.auth_user_id=(select auth.uid()) or
     ((select auth.jwt())->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')))
);
drop policy if exists insight_portfolio_read on public.predictive_insights;
create policy insight_portfolio_read on public.predictive_insights for select to authenticated using (
  exists(select 1 from public.customers c where c.customer_id=predictive_insights.customer_id and
    (c.auth_user_id=(select auth.uid()) or
     ((select auth.jwt())->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')))
);
