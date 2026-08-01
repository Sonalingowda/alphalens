import "server-only";

import type {
  DashboardBundle,
  DashboardDataResult,
  DashboardSnapshot,
  HealthResponse,
  MetricsResponse,
  ModelResponse,
  ResourceResponse,
  ApiEnvelope,
  ApiResult,
  LiveMarketSnapshot,
  MvpHealth,
  OpportunityDetail,
  OpportunityFilters,
  OpportunityPage,
} from "@/lib/types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function apiBaseUrl(): string {
  return (
    process.env.ALPHALENS_API_BASE_URL ?? DEFAULT_API_BASE_URL
  ).replace(/\/$/, "");
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}.`);
  }
  return (await response.json()) as T;
}

async function requestEnvelope<T>(path: string): Promise<ApiResult<T>> {
  try {
    const envelope = await request<ApiEnvelope<T>>(path);
    return {
      ok: true,
      data: envelope.data,
      responseHash: envelope.response_hash,
    };
  } catch (error) {
    return {
      ok: false,
      error:
        error instanceof Error ? error.message : "AlphaLens API is unavailable.",
    };
  }
}

function queryString(values: Record<string, string | undefined>): string {
  const parameters = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value) parameters.set(key, value);
  });
  return parameters.toString();
}

export function getMvpHealth(): Promise<ApiResult<MvpHealth>> {
  return requestEnvelope<MvpHealth>("/health");
}

export function getLiveMarket(
  instrument = "BTCUSDT",
  timeframe = "5m",
): Promise<ApiResult<LiveMarketSnapshot>> {
  const query = queryString({ instrument, timeframe });
  return requestEnvelope<LiveMarketSnapshot>(`/markets/live?${query}`);
}

export function getOpportunities(
  filters: OpportunityFilters,
): Promise<ApiResult<OpportunityPage>> {
  const query = queryString({
    instrument: filters.instrument,
    timeframe: filters.timeframe,
    stance: filters.stance,
    search: filters.search,
  });
  return requestEnvelope<OpportunityPage>(`/opportunities?${query}`);
}

export function getOpportunityDetail(
  opportunityId: string,
): Promise<ApiResult<OpportunityDetail>> {
  return requestEnvelope<OpportunityDetail>(
    `/opportunities/${encodeURIComponent(opportunityId)}`,
  );
}

export async function getDashboardBundle(): Promise<DashboardDataResult> {
  try {
    const [dashboard, health, model, metrics, resources] = await Promise.all([
      request<DashboardSnapshot>("/api/v1/dashboard"),
      request<HealthResponse>("/api/v1/health"),
      request<ModelResponse>("/api/v1/model"),
      request<MetricsResponse>("/api/v1/metrics"),
      request<ResourceResponse>("/api/v1/resources"),
    ]);
    const data: DashboardBundle = {
      dashboard,
      health,
      model,
      metrics,
      resources,
    };
    return { ok: true, data };
  } catch (error) {
    return {
      ok: false,
      error:
        error instanceof Error
          ? error.message
          : "Live Prediction API is unavailable.",
    };
  }
}
