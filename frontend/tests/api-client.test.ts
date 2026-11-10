import { afterEach, describe, expect, it, vi } from "vitest";

import { checkProtectedSession, fetchOpportunities } from "@/lib/api-client";

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

  it("classifies the exact sentinel not-found response as authorized", async () => {
    vi.stubEnv("NEXT_PUBLIC_ALPHALENS_API_BASE_URL", "http://127.0.0.1:18003");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { code: "entity.not_found" } }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(checkProtectedSession("opaque-test-token")).resolves.toEqual({
      status: 404,
      errorCode: "entity.not_found",
      authorization: "authorized",
    });
    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:18003/api/v1/paper-tracking/confirmation?opportunity_id=auth-check&opportunity_version_id=auth-check",
      expect.objectContaining({
        headers: {
          Accept: "application/json",
          Authorization: "Bearer opaque-test-token",
        },
      }),
    );
  });

  it("classifies an unauthenticated protected response as unauthenticated", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("unauthorized", { status: 401 })),
    );

    await expect(checkProtectedSession("opaque-test-token")).resolves.toEqual({
      status: 401,
      errorCode: null,
      authorization: "unauthenticated",
    });
  });

  it("does not treat an unrelated conflict as authentication proof", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ error: { code: "version.conflict" } }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(checkProtectedSession("opaque-test-token")).resolves.toEqual({
      status: 409,
      errorCode: "version.conflict",
      authorization: "unexpected",
    });
  });
});
