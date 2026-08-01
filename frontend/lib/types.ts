export type HealthResponse = {
  status: "healthy";
  api_version: string;
  artifact_status: "verified";
  artifact_identifier: string;
  read_only: boolean;
};

export type ModelResponse = {
  api_version: string;
  artifact_identifier: string;
  model_family: string;
  artifact_version: string;
  artifact_sha256: string;
  configuration_hash: string;
  feature_pipeline_version: string;
  target_version: string;
  target_name: string;
  horizon_observations: number;
  schema_hash: string;
  feature_count: number;
  ordered_feature_names: string[];
};

export type MetricsResponse = {
  api_version: string;
  request_count: number;
  successful_request_count: number;
  error_request_count: number;
  prediction_count: number;
  average_latency_microseconds: number;
  maximum_latency_microseconds: number;
  health: string;
};

export type ResourceResponse = {
  api_version: string;
  uptime_seconds: number;
  process_cpu_user_seconds: number;
  process_cpu_system_seconds: number;
  maximum_resident_set_bytes: number;
};

export type Prediction = {
  prediction_timestamp: string;
  predicted_forward_return: string;
  predicted_float_hex: string;
  evidence_hash: string;
  feature_vector_hash: string;
  inference_artifact_sha256: string;
  target_name?: string;
  target_version?: string;
  horizon_observations?: number;
};

export type TradingSignal = {
  prediction_timestamp: string;
  action: "BUY" | "HOLD" | "EXIT";
  predicted_forward_return: string;
  strategy_name: string;
  strategy_version: string;
  source_prediction_hash: string;
};

export type PortfolioSummary = {
  available: boolean;
  cash: string | null;
  portfolio_value: string | null;
  daily_pnl: string | null;
  unrealized_pnl: string | null;
  realized_pnl: string | null;
  open_position_count: number;
  closed_trade_count: number;
};

export type Order = {
  signal_timestamp: string;
  execution_timestamp: string;
  side: "BUY" | "SELL";
  reference_price: string;
  execution_price: string;
  quantity: string;
  gross_notional: string;
  transaction_cost: string;
  cash_delta: string;
  reason: string;
};

export type Trade = {
  entry_signal_timestamp: string;
  entry_timestamp: string;
  exit_signal_timestamp: string | null;
  exit_timestamp: string;
  quantity: string;
  entry_price: string;
  exit_price: string;
  gross_profit_loss: string;
  net_profit_loss: string;
  total_transaction_cost: string;
  return_fraction: string;
  holding_days: number;
  exit_reason: string;
};

export type RiskEvent = {
  timestamp: string;
  event_type: string;
  action: string;
  rule_names: string[];
  reason: string;
  requested_cash_allocation: string | null;
  approved_cash_allocation: string | null;
  reference_price: string | null;
  source: string;
  report_id: string;
};

export type PortfolioHistory = {
  timestamp: string;
  cash: string;
  position_quantity: string;
  position_market_value: string;
  portfolio_value: string;
  daily_return: string;
  open_position_count: number;
};

export type ChartPoint = {
  timestamp: string;
  value: string;
};

export type BacktestReport = {
  report_id: string;
  report_version: string;
  engine_version: string;
  generated_at: string;
  period_start: string;
  period_end: string;
  metrics: Record<string, string | number | null>;
  equity_curve: Array<{
    timestamp: string;
    portfolio_value: string;
  }>;
  trade_log: Trade[];
  signals: TradingSignal[];
  result_hash: string;
  configuration_hash: string;
};

export type DashboardSnapshot = {
  snapshot_version: string;
  generated_at: string;
  prediction: Prediction | null;
  signal: TradingSignal | null;
  confidence: {
    available: boolean;
    reason: string;
  };
  portfolio: PortfolioSummary;
  predictions: Prediction[];
  signals: TradingSignal[];
  orders: Order[];
  trades: Trade[];
  risk_events: RiskEvent[];
  portfolio_history: PortfolioHistory[];
  charts: {
    equity_curve: ChartPoint[];
    daily_returns: ChartPoint[];
    drawdown: ChartPoint[];
    prediction_history: ChartPoint[];
    trade_timeline: ChartPoint[];
    position_history: ChartPoint[];
  };
  backtest_reports: BacktestReport[];
  system: {
    api_version: string;
    database_status: string;
    model_family: string;
    model_version: string;
    artifact_identifier: string;
    artifact_sha256: string;
    artifact_configuration_hash: string;
    feature_pipeline_version: string;
    target_version: string;
    paper_engine_version: string | null;
    risk_framework_version: string | null;
    test_status: string;
  };
  settings: {
    read_only: boolean;
    session_name: string;
    asset_identifier: string;
    quote_currency: string;
    timeframe: string;
    execution_interval_seconds: number;
    market_history_observations: number;
    strategy: Record<string, unknown>;
    risk: Record<string, unknown>;
    portfolio: Record<string, unknown>;
  } | null;
  provenance: {
    paper_report_id: string | null;
    paper_result_hash: string | null;
    risk_report_id: string | null;
    risk_result_hash: string | null;
    backtest_report_ids: string[];
    inference_artifact_id: string;
  };
};

export type DashboardBundle = {
  dashboard: DashboardSnapshot;
  health: HealthResponse;
  model: ModelResponse;
  metrics: MetricsResponse;
  resources: ResourceResponse;
};

export type DashboardDataResult =
  | { ok: true; data: DashboardBundle }
  | { ok: false; error: string };

export type ApiEnvelope<T> = {
  contract_version: string;
  data: T;
  response_hash: string;
};

export type ApiResult<T> =
  | { ok: true; data: T; responseHash: string }
  | { ok: false; error: string };

export type MarketScope = {
  instrument: string;
  timeframe: string;
};

export type MarketCandle = {
  candle_id: string;
  timestamp: string;
  available_at: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
};

export type LiveMarketSnapshot = {
  contract_version: string;
  snapshot_id: string;
  scope: MarketScope;
  candles: MarketCandle[];
  complete: boolean;
  audit: {
    created_at: string;
    evidence_cutoff: string;
    available_at: string;
    result_hash: string;
  };
};

export type OpportunityDashboardItem = {
  opportunity_id: string;
  opportunity_version_id: string;
  scope: MarketScope;
  stance: "BUY" | "SELL";
  lifecycle_state: string;
  evidence_cutoff: string;
  available_at: string;
  freshness_state: string;
  rank: number;
  reason_codes: string[];
  has_plan: boolean;
  limitations: string[];
  detail_reference: string;
};

export type OpportunityPage = {
  contract_version: string;
  as_of?: string;
  generated_at?: string;
  scope?: MarketScope;
  items: OpportunityDashboardItem[];
  applied_filters: string[];
  sort: string;
  next_cursor?: string | null;
  freshness_status?: string;
  coverage_status?: string;
  partial_failures?: string[];
};

export type OpportunityDetail = {
  contract_version: string;
  detail_id: string;
  opportunity: {
    opportunity_id: string;
    opportunity_version_id: string;
    scope: MarketScope;
    stance: "BUY" | "SELL" | "WAIT";
    detected_at?: string;
    available_at?: string;
    [key: string]: unknown;
  };
  market_snapshot: LiveMarketSnapshot;
  indicators: Array<{
    feature_identifier: string;
    definition_version: string;
    output_name: string;
    value: string;
    unit: string;
    candle_timestamp: string;
    available_at: string;
  }>;
  evidence: {
    package_id: string;
    [key: string]: unknown;
  };
  explanation: {
    [key: string]: unknown;
  };
  lifecycle: {
    current_state?: string;
    [key: string]: unknown;
  };
  verification_status: string;
  audit: {
    evidence_cutoff: string;
    available_at: string;
    result_hash: string;
  };
};

export type MvpHealth = {
  status: "ready" | "degraded";
  service: string;
  api_version: string;
  read_only: boolean;
  authentication_required: boolean;
  components: {
    market_snapshots: "configured" | "unavailable";
    opportunity_dashboard: "configured";
    opportunity_detail: "configured";
  };
};

export type OpportunityFilters = {
  instrument: string;
  timeframe: string;
  stance?: "BUY" | "SELL";
  search?: string;
};
