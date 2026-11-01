import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";

function matchesConfiguredToken(candidate: string, configured: string): boolean {
  const left = Buffer.from(candidate);
  const right = Buffer.from(configured);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function POST(request: Request) {
  if (process.env.ALPHALENS_LOCAL_ONLY !== "true") {
    return NextResponse.json({ error: "Local-only access is disabled." }, { status: 404 });
  }
  const configured = process.env.ALPHALENS_LOCAL_ACCESS_TOKEN ?? "";
  const form = await request.formData();
  const token = String(form.get("token") ?? "");
  if (!configured || !matchesConfiguredToken(token, configured)) {
    return NextResponse.redirect(new URL("/local-login?error=invalid", request.url), 303);
  }
  const next = String(form.get("next") ?? "/");
  const destination = next.startsWith("/") && !next.startsWith("//") ? next : "/";
  const response = NextResponse.redirect(new URL(destination, request.url), 303);
  response.cookies.set("alphalens_local_session", configured, {
    httpOnly: true,
    sameSite: "lax",
    secure: new URL(request.url).protocol === "https:",
    path: "/",
  });
  return response;
}
