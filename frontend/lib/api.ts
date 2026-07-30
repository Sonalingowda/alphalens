import "server-only";

import type {
  DashboardBundle,
  DashboardDataResult,
  DashboardSnapshot,
  HealthResponse,
  MetricsResponse,
  ModelResponse,
  ResourceResponse,
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
