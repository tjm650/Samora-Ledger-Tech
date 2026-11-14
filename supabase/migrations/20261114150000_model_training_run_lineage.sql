-- Add explicit experiment tracking metadata for model training.
ALTER TABLE public.model_runs
  ADD COLUMN IF NOT EXISTS model_version_id uuid REFERENCES public.model_versions(model_version_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_model_runs_model_version ON public.model_runs(model_version_id);
