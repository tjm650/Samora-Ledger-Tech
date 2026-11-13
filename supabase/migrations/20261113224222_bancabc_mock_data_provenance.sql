alter table public.customers add column if not exists data_origin text not null default 'imported' check (data_origin in ('imported','mock'));
alter table public.transactions add column if not exists data_origin text not null default 'imported' check (data_origin in ('imported','mock'));
alter table public.customer_features add column if not exists data_origin text not null default 'imported' check (data_origin in ('imported','mock'));
alter table public.predictive_insights add column if not exists data_origin text not null default 'imported' check (data_origin in ('imported','mock'));
create table if not exists public.demo_seed_runs (
  seed_key text primary key,
  dataset_name text not null,
  customers_created integer not null default 0,
  transactions_created integer not null default 0,
  created_at timestamptz not null default now()
);
alter table public.demo_seed_runs enable row level security;
revoke all on public.demo_seed_runs from anon, authenticated;
grant all on public.demo_seed_runs to service_role;
