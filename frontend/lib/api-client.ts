import type { ApiEnvelope, ApiResult, OpportunityFilters, OpportunityPage } from "@/lib/types";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function apiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_ALPHALENS_API_BASE_URL ??
    process.env.ALPHALENS_API_BASE_URL ??
    DEFAULT_API_BASE_URL
  ).replace(/\/$/, "");
}

function queryString(values: Record<string, string | undefined>): string {
  const parameters = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value) parameters.set(key, value);
  });
  return parameters.toString();
}

type PaperTrackingConfirmation = {
  opportunity_id: string;
  opportunity_version_id: string;
  confirmed_scenario_hash: string;
};

type PaperTrackingSelection = {
  execution_id: string;
  position_id: string;
  opportunity_id: string;
  opportunity_version_id: string;
  status: string;
  selected_at: string;
  actor_id: string;
};

async function authenticatedRequest<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new Error("The paper-tracking request was rejected.");
  }
  return (await response.json()) as T;
}

export function confirmPaperTracking(
  token: string,
  opportunityId: string,
  opportunityVersionId: string,
): Promise<PaperTrackingConfirmation> {
  const query = queryString({
    opportunity_id: opportunityId,
    opportunity_version_id: opportunityVersionId,
  });
  return authenticatedRequest<PaperTrackingConfirmation>(
    `/api/v1/paper-tracking/confirmation?${query}`,
    token,
  );
}

export function selectPaperTracking(
  token: string,
  confirmation: PaperTrackingConfirmation,
): Promise<PaperTrackingSelection> {
  return authenticatedRequest<PaperTrackingSelection>(
    "/api/v1/paper-tracking/selections",
    token,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(confirmation),
    },
  );
}

function isApiEnvelope<T>(value: unknown): value is ApiEnvelope<T> {
  return (
    typeof value === "object" &&
    value !== null &&
    "contract_version" in value &&
    "data" in value &&
    "response_hash" in value
  );
}

async function clientRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(8_000),
  });
  if (!response.ok) {
    throw new Error(`API request failed with status ${response.status}.`);
  }
  return (await response.json()) as T;
}

async function clientRequestEnvelope<T>(path: string): Promise<ApiResult<T>> {
  try {
    const envelope = await clientRequest<unknown>(path);
    if (isApiEnvelope<T>(envelope)) {
      return {
        ok: true,
        data: envelope.data,
        responseHash: envelope.response_hash,
      };
    }
    return { ok: true, data: envelope as T, responseHash: "" };
  } catch (error) {
    return {
      ok: false,
      error:
        error instanceof Error ? error.message : "AlphaLens API is unavailable.",
    };
  }
}

export function fetchOpportunities(
  filters: OpportunityFilters,
  asOf: string = new Date().toISOString(),
): Promise<ApiResult<OpportunityPage>> {
  const query = queryString({
    as_of: asOf,
    instrument: filters.instrument,
    timeframe: filters.timeframe,
    stance: filters.stance,
    search: filters.search,
  });
  return clientRequestEnvelope<OpportunityPage>(`/api/v1/opportunities?${query}`);
}
