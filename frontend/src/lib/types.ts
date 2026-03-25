export type ApiError = {
  detail?: string;
};

export type HealthResponse = {
  status: string;
  version: string;
  env: string;
};

export type DashboardStatus = {
  ok: boolean;
  debug: boolean;
  auto_seed_demo: boolean;
  counts: Record<string, number>;
};

export type TransactionOut = {
  txn_id: string;
  sender_id: string;
  receiver_id: string;
  amount_usd: number;
  composite_risk_score: number;
  risk_label: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
};

export type TransactionListOut = {
  total: number;
  results: TransactionOut[];
};

export type TransactionScoreIn = {
  amount_usd: number;
  currency: string;
  payment_method?: string | null;
  txn_type?: string | null;
  timestamp?: string;
  is_cross_border: boolean;
  sender_country?: string | null;
  receiver_country?: string | null;
  ip_country?: string | null;
  channel?: string | null;
  pep_involved: boolean;
  dormant_days: number;
  recent_txn_count: number;
  recent_total_usd: number;
  graph_score: number;
};

export type TransactionScoreOut = {
  composite_risk_score: number;
  risk_label: string;
  severity?: string | null;
  alert_recommended: boolean;
  rule_score: number;
  ml_score: number;
  graph_score: number;
  ml_model_loaded?: boolean;
  is_cross_border_used?: boolean;
  data_warnings?: string[];
  triggered_rules: string[];
  reasons: string[];
};

export type TransactionCreate = {
  txn_id: string;
  sender_id: string;
  receiver_id: string;
  amount_usd: number;
  amount_local: number;
  currency: string;
  fx_rate_to_usd: number;
  payment_method?: string | null;
  txn_type?: string | null;
  timestamp: string;
  is_cross_border: boolean;
  sender_country?: string | null;
  receiver_country?: string | null;
  device_fingerprint?: string | null;
  ip_country?: string | null;
  channel?: string | null;
};

export type AlertOut = {
  alert_id: string;
  txn_id?: string | null;
  user_id?: string | null;
  alert_rule?: string | null;
  severity?: string | null;
  composite_risk_score?: number | null;
  rule_score?: number | null;
  ml_score?: number | null;
  graph_score?: number | null;
  alert_created_at?: string | null;
  alert_resolved_at?: string | null;
  resolution_time_hours?: number | null;
  assigned_analyst?: string | null;
  alert_status?: string | null;
  sar_filed?: boolean | null;
  false_positive?: boolean | null;
  notes?: string | null;
};

export type AlertListOut = {
  total: number;
  results: AlertOut[];
};

export type AlertUpdate = {
  alert_status?: string | null;
  notes?: string | null;
  sar_filed?: boolean | null;
  false_positive?: boolean | null;
};

export type RiskModelInfoOut = {
  loaded: boolean;
  model?: string | null;
  model_type?: string | null;
  feature_names?: string[] | null;
  load_error?: string | null;
};

export type MetricOut = {
  roc_auc?: number | null;
  average_precision?: number | null;
};

export type RiskTrainIn = {
  max_rows: number;
  test_size: number;
  random_state: number;
  split_strategy?: string;
};

export type RiskEvaluateIn = {
  max_rows: number;
  top_n: number;
  split_strategy?: string;
  test_size?: number;
  random_state?: number;
};

export type RiskTrainOut = {
  model: string;
  split_strategy?: string;
  cutoff_timestamp?: string | null;
  train_rows?: number | null;
  test_rows?: number | null;
  rows: number;
  positives: number;
  prevalence: number;
  ml: MetricOut;
  feature_columns: string[];
  notes: string[];
};

export type RiskEvaluateOut = {
  split_strategy?: string;
  cutoff_timestamp?: string | null;
  train_rows?: number | null;
  test_rows?: number | null;
  rows: number;
  positives: number;
  prevalence: number;
  ml: MetricOut;
  composite: MetricOut;
  top: Record<string, unknown>[];
  notes: string[];
};

export type ScoreComponentOut = {
  score: number;
  weight: number;
  contribution: number;
};

export type ScoreBreakdownOut = {
  rule: ScoreComponentOut;
  ml: ScoreComponentOut;
  graph: ScoreComponentOut;
};

export type FeatureHighlightOut = {
  label: string;
  value: string;
  why?: string | null;
};

export type RiskExplainOut = {
  entity_type: "transaction" | "alert" | string;
  entity_id: string;
  risk_label?: string | null;
  composite_risk_score?: number | null;
  breakdown?: ScoreBreakdownOut | null;
  triggered_rules?: string[];
  reasons?: string[];
  highlights?: FeatureHighlightOut[];
};

