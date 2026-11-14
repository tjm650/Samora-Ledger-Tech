-- Finalize provenance values, seed the versioned feature contract, and avoid duplicate indexes.
ALTER TABLE public.customers DROP CONSTRAINT IF EXISTS customers_data_origin_check;
ALTER TABLE public.customers ADD CONSTRAINT customers_data_origin_check
  CHECK (data_origin IN ('imported','mock','synthetic','test'));
ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS transactions_data_origin_check;
ALTER TABLE public.transactions ADD CONSTRAINT transactions_data_origin_check
  CHECK (data_origin IN ('imported','mock','synthetic','test'));

DROP INDEX IF EXISTS public.idx_transactions_customer_timestamp;
DROP INDEX IF EXISTS public.idx_customer_feature_history_customer_date;

INSERT INTO public.feature_definitions
(feature_key, display_name, description, data_type, source_tables, calculation_spec, lookback_days, null_policy, feature_group, version)
VALUES
('recency_days','Transaction recency','Days since the most recent eligible posted transaction as of the feature cutoff.','integer',ARRAY['transactions'], '{"aggregation":"cutoff_date - max(timestamp)","filters":{"transaction_status":"posted"}}',365,'preserve','activity','1.0'),
('frequency_7d','7-day transaction frequency','Count of eligible posted transactions in the preceding 7 days.','integer',ARRAY['transactions'],'{"aggregation":"count","window_days":7,"filters":{"transaction_status":"posted"}}',7,'zero_when_no_activity','activity','1.0'),
('frequency_30d','30-day transaction frequency','Count of eligible posted transactions in the preceding 30 days.','integer',ARRAY['transactions'],'{"aggregation":"count","window_days":30,"filters":{"transaction_status":"posted"}}',30,'zero_when_no_activity','activity','1.0'),
('frequency_90d','90-day transaction frequency','Count of eligible posted transactions in the preceding 90 days.','integer',ARRAY['transactions'],'{"aggregation":"count","window_days":90,"filters":{"transaction_status":"posted"}}',90,'zero_when_no_activity','activity','1.0'),
('frequency_180d','180-day transaction frequency','Count of eligible posted transactions in the preceding 180 days.','integer',ARRAY['transactions'],'{"aggregation":"count","window_days":180,"filters":{"transaction_status":"posted"}}',180,'zero_when_no_activity','activity','1.0'),
('monetary_spend_30d','30-day debit spend','Sum of posted debit transaction amounts in the preceding 30 days.','numeric',ARRAY['transactions'],'{"aggregation":"sum","amount_field":"amount","filters":{"transaction_type":"Debit","transaction_status":"posted"}}',30,'zero_when_no_activity','monetary','1.0'),
('monetary_spend_60d','60-day debit spend','Sum of posted debit transaction amounts in the preceding 60 days.','numeric',ARRAY['transactions'],'{"aggregation":"sum","amount_field":"amount","filters":{"transaction_type":"Debit","transaction_status":"posted"}}',60,'zero_when_no_activity','monetary','1.0'),
('monetary_spend_90d','90-day debit spend','Sum of posted debit transaction amounts in the preceding 90 days.','numeric',ARRAY['transactions'],'{"aggregation":"sum","amount_field":"amount","filters":{"transaction_type":"Debit","transaction_status":"posted"}}',90,'zero_when_no_activity','monetary','1.0'),
('monetary_spend_180d','180-day debit spend','Sum of posted debit transaction amounts in the preceding 180 days.','numeric',ARRAY['transactions'],'{"aggregation":"sum","amount_field":"amount","filters":{"transaction_type":"Debit","transaction_status":"posted"}}',180,'zero_when_no_activity','monetary','1.0'),
('credit_inflow_90d','90-day credit inflow','Sum of posted credit transaction amounts in the preceding 90 days.','numeric',ARRAY['transactions'],'{"aggregation":"sum","amount_field":"amount","filters":{"transaction_type":"Credit","transaction_status":"posted"}}',90,'zero_when_no_activity','cashflow','1.0'),
('debit_outflow_90d','90-day debit outflow','Sum of posted debit transaction amounts in the preceding 90 days.','numeric',ARRAY['transactions'],'{"aggregation":"sum","amount_field":"amount","filters":{"transaction_type":"Debit","transaction_status":"posted"}}',90,'zero_when_no_activity','cashflow','1.0'),
('average_transaction_value_90d','90-day average transaction value','Average absolute transaction amount over the preceding 90 days.','numeric',ARRAY['transactions'],'{"aggregation":"avg","amount_field":"amount","filters":{"transaction_status":"posted"}}',90,'preserve','monetary','1.0'),
('active_days_90d','Active transaction days','Distinct calendar days with eligible posted transactions in the preceding 90 days.','integer',ARRAY['transactions'],'{"aggregation":"count_distinct","field":"timestamp::date","filters":{"transaction_status":"posted"}}',90,'zero_when_no_activity','activity','1.0'),
('channel_diversity_90d','Channel diversity','Count of distinct transaction channels used in the preceding 90 days.','integer',ARRAY['transactions'],'{"aggregation":"count_distinct","field":"channel","filters":{"transaction_status":"posted"}}',90,'zero_when_no_activity','engagement','1.0'),
('category_diversity_90d','Category diversity','Count of distinct merchant categories used in the preceding 90 days.','integer',ARRAY['transactions'],'{"aggregation":"count_distinct","field":"merchant_category","filters":{"transaction_status":"posted"}}',90,'zero_when_no_activity','engagement','1.0'),
('product_count','Active product count','Count of distinct active customer products as of the feature cutoff.','integer',ARRAY['customer_products'],'{"aggregation":"count_distinct","field":"product_id","filters":{"status":"active"}}',null,'zero_when_no_activity','relationship','1.0')
ON CONFLICT (feature_key) DO UPDATE SET
 display_name=EXCLUDED.display_name, description=EXCLUDED.description,
 data_type=EXCLUDED.data_type, source_tables=EXCLUDED.source_tables,
 calculation_spec=EXCLUDED.calculation_spec, lookback_days=EXCLUDED.lookback_days,
 null_policy=EXCLUDED.null_policy, feature_group=EXCLUDED.feature_group,
 version=EXCLUDED.version, is_active=true, updated_at=now();
