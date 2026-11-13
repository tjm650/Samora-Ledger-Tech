create index if not exists idx_customer_products_product on public.customer_products(product_id);
create index if not exists idx_product_recommendations_product on public.product_recommendations(product_id);
create index if not exists idx_recommendation_outcomes_recommendation on public.recommendation_outcomes(recommendation_id);
create index if not exists idx_recommendation_outcomes_actor on public.recommendation_outcomes(recorded_by);
create index if not exists idx_customer_churn_outcomes_actor on public.customer_churn_outcomes(recorded_by);