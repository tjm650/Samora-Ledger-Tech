create extension if not exists pgcrypto;
create table if not exists public.customers (
 customer_id uuid primary key default gen_random_uuid(),
 auth_user_id uuid unique references auth.users(id) on delete set null,
 full_name text not null, email text not null unique,
 account_tier text not null default 'Standard' check(account_tier in ('Standard','Gold','Platinum')),
 created_at timestamptz not null default now()
);
create table if not exists public.transactions (
 transaction_id uuid primary key default gen_random_uuid(),
 customer_id uuid not null references public.customers(customer_id) on delete cascade,
 "timestamp" timestamptz not null, amount numeric(18,2) not null check(amount >= 0),
 transaction_type text not null check(transaction_type in ('Credit','Debit')),
 merchant_category text not null check(merchant_category in ('Groceries','Travel','Luxury','Utilities','Salary','ATM','Transfers')),
 channel text not null check(channel in ('Mobile App','Web','POS','ATM')),
 post_transaction_balance numeric(18,2) not null check(post_transaction_balance >= 0),
 created_at timestamptz not null default now()
);
create table if not exists public.customer_features (
 customer_id uuid primary key references public.customers(customer_id) on delete cascade,
 recency_days integer not null default 0, frequency_30d integer not null default 0,
 monetary_spend_90d numeric(18,2) not null default 0, balance_avg_30d numeric(18,2) not null default 0,
 velocity_score numeric(12,4) not null default 1, discretionary_spend_ratio numeric(8,5) not null default 0,
 salary_disruption_flag boolean not null default false, balance_drawdown_pct numeric(8,5) not null default 0,
 behavior_segment text, updated_at timestamptz not null default now()
);
create table if not exists public.predictive_insights (
 insight_id uuid primary key default gen_random_uuid(),
 customer_id uuid not null unique references public.customers(customer_id) on delete cascade,
 churn_risk_score numeric(5,2) not null check(churn_risk_score between 0 and 100),
 primary_churn_driver text not null, recommended_product text,
 prescriptive_action text not null, evaluated_at timestamptz not null default now()
);
create index if not exists idx_transactions_customer_time on public.transactions(customer_id,"timestamp" desc);
create index if not exists idx_transactions_timestamp on public.transactions("timestamp" desc);
create index if not exists idx_features_customer on public.customer_features(customer_id);
create index if not exists idx_insights_customer on public.predictive_insights(customer_id);
create index if not exists idx_insights_churn on public.predictive_insights(churn_risk_score desc);
alter table public.customers enable row level security;
alter table public.transactions enable row level security;
alter table public.customer_features enable row level security;
alter table public.predictive_insights enable row level security;
drop policy if exists customer_self_read on public.customers;
create policy customer_self_read on public.customers for select to authenticated using (
 auth_user_id = auth.uid() or (auth.jwt()->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')
);
drop policy if exists customer_self_update on public.customers;
create policy customer_self_update on public.customers for update to authenticated using(auth_user_id=auth.uid());
drop policy if exists transaction_portfolio_read on public.transactions;
create policy transaction_portfolio_read on public.transactions for select to authenticated using (
 exists(select 1 from public.customers c where c.customer_id=transactions.customer_id and
 (c.auth_user_id=auth.uid() or (auth.jwt()->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')))
);
drop policy if exists feature_portfolio_read on public.customer_features;
create policy feature_portfolio_read on public.customer_features for select to authenticated using (
 exists(select 1 from public.customers c where c.customer_id=customer_features.customer_id and
 (c.auth_user_id=auth.uid() or (auth.jwt()->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')))
);
drop policy if exists insight_portfolio_read on public.predictive_insights;
create policy insight_portfolio_read on public.predictive_insights for select to authenticated using (
 exists(select 1 from public.customers c where c.customer_id=predictive_insights.customer_id and
 (c.auth_user_id=auth.uid() or (auth.jwt()->'app_metadata'->>'role') in ('admin','analyst','relationship_manager')))
);
grant select on public.customers,public.transactions,public.customer_features,public.predictive_insights to authenticated;
grant all on public.customers,public.transactions,public.customer_features,public.predictive_insights to service_role;
