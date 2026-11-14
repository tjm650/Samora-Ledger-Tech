-- Samora Ledger Tech: model-data foundation
-- Adds data lineage, expanded behavioural features, labelled outcomes,
-- reproducible training datasets, evaluation, prediction history and monitoring.

ALTER TABLE public.customers
  ADD COLUMN IF NOT EXISTS external_customer_ref text,
  ADD COLUMN IF NOT EXISTS customer_type text,
  ADD COLUMN IF NOT EXISTS relationship_start_date date,
  ADD COLUMN IF NOT EXISTS branch_code text,
  ADD COLUMN IF NOT EXISTS region_code text,
  ADD COLUMN IF NOT EXISTS source_system text,
  ADD COLUMN IF NOT EXISTS import_batch_id uuid;

ALTER TABLE public.transactions
  ADD COLUMN IF NOT EXISTS external_transaction_ref text,
  ADD COLUMN IF NOT EXISTS account_ref text,
  ADD COLUMN IF NOT EXISTS currency_code char(3),
  ADD COLUMN IF NOT EXISTS transaction_status text NOT NULL DEFAULT 'posted',
  ADD COLUMN IF NOT EXISTS source_system text,
  ADD COLUMN IF NOT EXISTS import_batch_id uuid,
  ADD COLUMN IF NOT EXISTS value_date date,
  ADD COLUMN IF NOT EXISTS counterparty_category text;

ALTER TABLE public.customer_features
  ADD COLUMN IF NOT EXISTS frequency_7d integer,
  ADD COLUMN IF NOT EXISTS frequency_90d integer,
  ADD COLUMN IF NOT EXISTS frequency_180d integer,
  ADD COLUMN IF NOT EXISTS monetary_spend_30d numeric(20,4),
  ADD COLUMN IF NOT EXISTS monetary_spend_60d numeric(20,4),
  ADD COLUMN IF NOT EXISTS monetary_spend_180d numeric(20,4),
  ADD COLUMN IF NOT EXISTS credit_inflow_30d numeric(20,4),
  ADD COLUMN IF NOT EXISTS credit_inflow_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS debit_outflow_30d numeric(20,4),
  ADD COLUMN IF NOT EXISTS debit_outflow_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS average_transaction_value_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS transaction_count_90d integer,
  ADD COLUMN IF NOT EXISTS active_days_90d integer,
  ADD COLUMN IF NOT EXISTS channel_diversity_90d integer,
  ADD COLUMN IF NOT EXISTS category_diversity_90d integer,
  ADD COLUMN IF NOT EXISTS salary_inflow_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS product_count integer,
  ADD COLUMN IF NOT EXISTS feature_engine_version text,
  ADD COLUMN IF NOT EXISTS feature_as_of timestamptz,
  ADD COLUMN IF NOT EXISTS feature_quality_status text NOT NULL DEFAULT 'unverified';

ALTER TABLE public.customer_feature_history
  ADD COLUMN IF NOT EXISTS frequency_7d integer,
  ADD COLUMN IF NOT EXISTS frequency_90d integer,
  ADD COLUMN IF NOT EXISTS frequency_180d integer,
  ADD COLUMN IF NOT EXISTS monetary_spend_180d numeric(20,4),
  ADD COLUMN IF NOT EXISTS credit_inflow_30d numeric(20,4),
  ADD COLUMN IF NOT EXISTS credit_inflow_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS debit_outflow_30d numeric(20,4),
  ADD COLUMN IF NOT EXISTS debit_outflow_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS transaction_count_90d integer,
  ADD COLUMN IF NOT EXISTS active_days_90d integer,
  ADD COLUMN IF NOT EXISTS channel_diversity_90d integer,
  ADD COLUMN IF NOT EXISTS category_diversity_90d integer,
  ADD COLUMN IF NOT EXISTS salary_inflow_90d numeric(20,4),
  ADD COLUMN IF NOT EXISTS product_count integer,
  ADD COLUMN IF NOT EXISTS feature_quality_status text,
  ADD COLUMN IF NOT EXISTS source_data_cutoff timestamptz,
  ADD COLUMN IF NOT EXISTS feature_values jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.model_versions
  ADD COLUMN IF NOT EXISTS algorithm text,
  ADD COLUMN IF NOT EXISTS target_name text,
  ADD COLUMN IF NOT EXISTS task_type text,
  ADD COLUMN IF NOT EXISTS feature_schema_version text,
  ADD COLUMN IF NOT EXISTS hyperparameters jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS training_dataset_id uuid,
  ADD COLUMN IF NOT EXISTS artifact_uri text,
  ADD COLUMN IF NOT EXISTS artifact_checksum text,
  ADD COLUMN IF NOT EXISTS training_started_at timestamptz,
  ADD COLUMN IF NOT EXISTS trained_at timestamptz,
  ADD COLUMN IF NOT EXISTS validation_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS approval_status text NOT NULL DEFAULT 'experimental',
  ADD COLUMN IF NOT EXISTS approved_at timestamptz,
  ADD COLUMN IF NOT EXISTS approved_by text,
  ADD COLUMN IF NOT EXISTS retired_at timestamptz,
  ADD COLUMN IF NOT EXISTS code_commit_sha text;

ALTER TABLE public.model_runs
  ADD COLUMN IF NOT EXISTS run_type text NOT NULL DEFAULT 'inference',
  ADD COLUMN IF NOT EXISTS dataset_id uuid,
  ADD COLUMN IF NOT EXISTS data_cutoff_at timestamptz,
  ADD COLUMN IF NOT EXISTS feature_schema_version text,
  ADD COLUMN IF NOT EXISTS code_commit_sha text,
  ADD COLUMN IF NOT EXISTS environment_name text,
  ADD COLUMN IF NOT EXISTS warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS run_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.customer_churn_outcomes
  ADD COLUMN IF NOT EXISTS outcome_window_start date,
  ADD COLUMN IF NOT EXISTS outcome_window_end date,
  ADD COLUMN IF NOT EXISTS label_definition_version text,
  ADD COLUMN IF NOT EXISTS label_confidence text NOT NULL DEFAULT 'unverified',
  ADD COLUMN IF NOT EXISTS verified_at timestamptz,
  ADD COLUMN IF NOT EXISTS data_origin text NOT NULL DEFAULT 'imported';

ALTER TABLE public.recommendation_outcomes
  ADD COLUMN IF NOT EXISTS exposure_at timestamptz,
  ADD COLUMN IF NOT EXISTS conversion_at timestamptz,
  ADD COLUMN IF NOT EXISTS revenue_amount numeric(20,4),
  ADD COLUMN IF NOT EXISTS currency_code char(3),
  ADD COLUMN IF NOT EXISTS campaign_ref text,
  ADD COLUMN IF NOT EXISTS data_origin text NOT NULL DEFAULT 'imported';

ALTER TABLE public.product_recommendations
  ADD COLUMN IF NOT EXISTS model_version_id uuid REFERENCES public.model_versions(model_version_id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS model_run_id uuid REFERENCES public.model_runs(model_run_id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS feature_snapshot_id uuid REFERENCES public.customer_feature_history(feature_snapshot_id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS eligibility_status text NOT NULL DEFAULT 'not_assessed',
  ADD COLUMN IF NOT EXISTS suitability_status text NOT NULL DEFAULT 'not_assessed',
  ADD COLUMN IF NOT EXISTS recommendation_source text NOT NULL DEFAULT 'rules',
  ADD COLUMN IF NOT EXISTS explanation jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.data_import_batches (
  import_batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_system text NOT NULL,
  source_dataset text,
  source_file_name text,
  data_origin text NOT NULL CHECK (data_origin IN ('imported','mock','synthetic','test')),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','validating','loaded','partially_loaded','failed','rejected')),
  currency_code char(3),
  source_row_count bigint,
  inserted_row_count bigint NOT NULL DEFAULT 0,
  rejected_row_count bigint NOT NULL DEFAULT 0,
  checksum_sha256 text,
  schema_version text,
  imported_at timestamptz,
  completed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.data_quality_runs (
  quality_run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  import_batch_id uuid REFERENCES public.data_import_batches(import_batch_id) ON DELETE SET NULL,
  dataset_name text NOT NULL,
  check_suite_version text NOT NULL,
  status text NOT NULL CHECK (status IN ('passed','warning','failed')),
  rows_checked bigint NOT NULL DEFAULT 0,
  issue_count bigint NOT NULL DEFAULT 0,
  error_count bigint NOT NULL DEFAULT 0,
  warning_count bigint NOT NULL DEFAULT 0,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  executed_at timestamptz NOT NULL DEFAULT now(),
  execution_ms bigint
);

CREATE TABLE IF NOT EXISTS public.data_quality_issues (
  quality_issue_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  quality_run_id uuid NOT NULL REFERENCES public.data_quality_runs(quality_run_id) ON DELETE CASCADE,
  dataset_name text NOT NULL,
  rule_code text NOT NULL,
  severity text NOT NULL CHECK (severity IN ('error','warning','info')),
  affected_rows bigint NOT NULL DEFAULT 0,
  sample_record_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
  description text NOT NULL,
  remediation text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.feature_definitions (
  feature_key text PRIMARY KEY,
  display_name text NOT NULL,
  description text NOT NULL,
  data_type text NOT NULL CHECK (data_type IN ('integer','numeric','boolean','text','date','timestamp','json')),
  source_tables text[] NOT NULL DEFAULT '{}',
  calculation_spec jsonb NOT NULL DEFAULT '{}'::jsonb,
  lookback_days integer,
  null_policy text NOT NULL DEFAULT 'preserve',
  feature_group text NOT NULL,
  version text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.model_datasets (
  dataset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dataset_name text NOT NULL,
  dataset_version text NOT NULL,
  model_type text NOT NULL,
  target_name text,
  data_origin text NOT NULL CHECK (data_origin IN ('imported','mock','synthetic','mixed')),
  source_import_batch_ids uuid[] NOT NULL DEFAULT '{}',
  feature_schema_version text NOT NULL,
  label_definition_version text,
  observation_start timestamptz,
  observation_end timestamptz,
  label_window_start timestamptz,
  label_window_end timestamptz,
  row_count bigint NOT NULL DEFAULT 0,
  customer_count bigint NOT NULL DEFAULT 0,
  feature_columns text[] NOT NULL DEFAULT '{}',
  excluded_columns text[] NOT NULL DEFAULT '{}',
  split_strategy text,
  dataset_checksum text,
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(dataset_name, dataset_version)
);

ALTER TABLE public.model_versions
  ADD CONSTRAINT model_versions_training_dataset_fk
  FOREIGN KEY (training_dataset_id) REFERENCES public.model_datasets(dataset_id) ON DELETE SET NULL;
ALTER TABLE public.model_runs
  ADD CONSTRAINT model_runs_dataset_fk
  FOREIGN KEY (dataset_id) REFERENCES public.model_datasets(dataset_id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS public.model_evaluations (
  evaluation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id uuid NOT NULL REFERENCES public.model_versions(model_version_id) ON DELETE CASCADE,
  model_run_id uuid REFERENCES public.model_runs(model_run_id) ON DELETE SET NULL,
  dataset_id uuid REFERENCES public.model_datasets(dataset_id) ON DELETE SET NULL,
  evaluation_name text NOT NULL,
  split_name text NOT NULL CHECK (split_name IN ('train','validation','test','out_of_time','cross_validation','backtest')),
  evaluated_at timestamptz NOT NULL DEFAULT now(),
  sample_count bigint NOT NULL DEFAULT 0,
  positive_count bigint,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  confusion_matrix jsonb,
  calibration jsonb,
  threshold_analysis jsonb,
  segment_metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  acceptance_status text NOT NULL DEFAULT 'not_reviewed' CHECK (acceptance_status IN ('not_reviewed','passed','failed','conditional')),
  reviewer text,
  notes text
);

CREATE TABLE IF NOT EXISTS public.model_predictions (
  prediction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id uuid NOT NULL REFERENCES public.customers(customer_id) ON DELETE CASCADE,
  model_version_id uuid NOT NULL REFERENCES public.model_versions(model_version_id) ON DELETE RESTRICT,
  model_run_id uuid REFERENCES public.model_runs(model_run_id) ON DELETE SET NULL,
  feature_snapshot_id uuid REFERENCES public.customer_feature_history(feature_snapshot_id) ON DELETE SET NULL,
  prediction_type text NOT NULL,
  target_name text,
  score numeric(18,8),
  predicted_class text,
  prediction_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  explanation jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric(8,7),
  prediction_at timestamptz NOT NULL DEFAULT now(),
  prediction_horizon_days integer,
  data_origin text NOT NULL DEFAULT 'imported' CHECK (data_origin IN ('imported','mock','synthetic','mixed')),
  superseded_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (score IS NULL OR score BETWEEN 0 AND 1),
  CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS public.model_monitoring_metrics (
  monitoring_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  model_version_id uuid NOT NULL REFERENCES public.model_versions(model_version_id) ON DELETE CASCADE,
  model_run_id uuid REFERENCES public.model_runs(model_run_id) ON DELETE SET NULL,
  metric_date date NOT NULL,
  window_start timestamptz NOT NULL,
  window_end timestamptz NOT NULL,
  monitoring_type text NOT NULL CHECK (monitoring_type IN ('feature_drift','prediction_drift','performance','data_quality','operational','business_outcome')),
  metric_name text NOT NULL,
  metric_value numeric(24,10),
  baseline_value numeric(24,10),
  threshold_value numeric(24,10),
  status text NOT NULL DEFAULT 'normal' CHECK (status IN ('normal','warning','critical','insufficient_data')),
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(model_version_id, metric_date, monitoring_type, metric_name, dimensions)
);

CREATE INDEX IF NOT EXISTS idx_transactions_customer_timestamp ON public.transactions(customer_id, "timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_import_batch ON public.transactions(import_batch_id) WHERE import_batch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customers_external_ref ON public.customers(source_system, external_customer_ref) WHERE external_customer_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_customer_feature_history_customer_date ON public.customer_feature_history(customer_id, calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_versions_training_dataset ON public.model_versions(training_dataset_id);
CREATE INDEX IF NOT EXISTS idx_model_runs_dataset ON public.model_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_model_evaluations_version_date ON public.model_evaluations(model_version_id, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_evaluations_run ON public.model_evaluations(model_run_id);
CREATE INDEX IF NOT EXISTS idx_model_evaluations_dataset ON public.model_evaluations(dataset_id);
CREATE INDEX IF NOT EXISTS idx_model_predictions_customer_date ON public.model_predictions(customer_id, prediction_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_predictions_type_date ON public.model_predictions(prediction_type, prediction_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_predictions_version_date ON public.model_predictions(model_version_id, prediction_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_predictions_run ON public.model_predictions(model_run_id);
CREATE INDEX IF NOT EXISTS idx_model_predictions_feature_snapshot ON public.model_predictions(feature_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_model_monitoring_version_date ON public.model_monitoring_metrics(model_version_id, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_model_monitoring_run ON public.model_monitoring_metrics(model_run_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_issues_run ON public.data_quality_issues(quality_run_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_runs_import_batch ON public.data_quality_runs(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_runs_dataset_date ON public.data_quality_runs(dataset_name, executed_at DESC);
CREATE INDEX IF NOT EXISTS idx_import_batches_source_date ON public.data_import_batches(source_system, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_model_version ON public.product_recommendations(model_version_id);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_model_run ON public.product_recommendations(model_run_id);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_feature_snapshot ON public.product_recommendations(feature_snapshot_id);

-- Server-only access: RLS plus no direct client-role privileges.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'data_import_batches','data_quality_runs','data_quality_issues',
    'feature_definitions','model_datasets','model_evaluations',
    'model_predictions','model_monitoring_metrics'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon, authenticated', t);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role', t);
  END LOOP;
END $$;

REVOKE ALL ON TABLE public.model_predictions, public.model_evaluations,
  public.model_monitoring_metrics, public.model_datasets,
  public.data_quality_runs, public.data_quality_issues,
  public.data_import_batches, public.feature_definitions
FROM PUBLIC;
