# First administrator setup

The redesigned workspace requires Supabase Auth. Public sign-up is disabled, and staff roles are read only from trusted `app_metadata`.

1. In the Supabase Dashboard, open **Authentication → Users** and create or invite your own work account.
2. Open **SQL Editor** for the same Supabase project and run the statement below, replacing the email with the exact invited account email.
3. Sign in through the Samora Ledger Tech **Staff sign in** page. The backend will synchronise the authenticated user into `public.staff_profiles`.

```sql
update auth.users
set raw_app_meta_data =
  coalesce(raw_app_meta_data, '{}'::jsonb) ||
  jsonb_build_object('role', 'admin')
where lower(email) = lower('YOUR_WORK_EMAIL@example.com');
```

Verify that exactly one account was updated. If zero rows were updated, confirm the user exists under Authentication → Users and check the email spelling.

```sql
select id, email, raw_app_meta_data->>'role' as trusted_role
from auth.users
where lower(email) = lower('YOUR_WORK_EMAIL@example.com');
```

Only a trusted project administrator should run this SQL. Do not put service-role credentials in the browser, frontend environment variables, or a public repository. Do not assign staff roles through `user_metadata`; users can edit that metadata themselves.

Additional staff roles are `executive`, `analyst`, and `relationship_manager`. Provision them through the trusted Supabase Auth administration process using the same approach, with the appropriate role value.
