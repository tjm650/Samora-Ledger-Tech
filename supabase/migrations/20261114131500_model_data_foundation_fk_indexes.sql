-- Add lineage foreign keys and indexes for model/data foundation.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='customers_import_batch_fk') THEN
    ALTER TABLE public.customers ADD CONSTRAINT customers_import_batch_fk
      FOREIGN KEY (import_batch_id) REFERENCES public.data_import_batches(import_batch_id) ON DELETE SET NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='transactions_import_batch_fk') THEN
    ALTER TABLE public.transactions ADD CONSTRAINT transactions_import_batch_fk
      FOREIGN KEY (import_batch_id) REFERENCES public.data_import_batches(import_batch_id) ON DELETE SET NULL;
  END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_data_quality_runs_import_batch ON public.data_quality_runs(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_model_evaluations_run ON public.model_evaluations(model_run_id);
CREATE INDEX IF NOT EXISTS idx_model_evaluations_dataset ON public.model_evaluations(dataset_id);
CREATE INDEX IF NOT EXISTS idx_model_monitoring_run ON public.model_monitoring_metrics(model_run_id);
CREATE INDEX IF NOT EXISTS idx_model_predictions_run ON public.model_predictions(model_run_id);
CREATE INDEX IF NOT EXISTS idx_model_predictions_feature_snapshot ON public.model_predictions(feature_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_model_runs_dataset ON public.model_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_model_versions_training_dataset ON public.model_versions(training_dataset_id);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_model_version ON public.product_recommendations(model_version_id);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_model_run ON public.product_recommendations(model_run_id);
CREATE INDEX IF NOT EXISTS idx_product_recommendations_feature_snapshot ON public.product_recommendations(feature_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_customers_import_batch ON public.customers(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_transactions_import_batch_fk ON public.transactions(import_batch_id);
