import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchOpportunities } from "@/lib/api-client";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("browser API endpoint selection", () => {
  it("uses the public browser API base instead of the server-only fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_ALPHALENS_API_BASE_URL", "http://127.0.0.1:18003");
    vi.stubEnv("ALPHALENS_API_BASE_URL", "http://127.0.0.1:8000");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            contract_version: "1.0.0",
            data: { contract_version: "1.0.0", items: [] },
            response_hash: "c".repeat(64),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const result = await fetchOpportunities({
      instrument: "BTCUSDT",
      timeframe: "5m",
    });

    expect(result.ok).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(
        /^http:\/\/127\.0\.0\.1:18003\/api\/v1\/opportunities\?/,
      ),
      expect.objectContaining({
        headers: { Accept: "application/json" },
      }),
    );
  });
});
