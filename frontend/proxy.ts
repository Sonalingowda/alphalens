import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

const localOnly = process.env.ALPHALENS_LOCAL_ONLY === "true";
const localAccessToken = process.env.ALPHALENS_LOCAL_ACCESS_TOKEN ?? "";

function localOnlyMiddleware(request: NextRequest) {
  const hostname = request.nextUrl.hostname;
  const path = request.nextUrl.pathname;
  const loopback = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
  if (!loopback || !localAccessToken) {
    return new NextResponse("Local-only authentication is unavailable.", { status: 503 });
  }
  if (path === "/local-login" || path === "/api/local-auth/login" || path === "/api/local-auth/logout") {
    return NextResponse.next();
  }
  if (request.headers.get("cookie")?.split(";").some((value) => value.trim() === `alphalens_local_session=${localAccessToken}`)) {
    return NextResponse.next();
  }
  if (request.headers.get("accept")?.includes("text/html")) {
    const login = new URL("/local-login", request.nextUrl.origin);
    login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(login);
  }
  return new NextResponse("Local authentication required.", {
    status: 401,
    headers: { "WWW-Authenticate": "Local" },
  });
}

// LOCAL_ONLY is an explicit, loopback-bound owner mode. The legacy demo flag
// never disables authentication; production and non-local environments retain
// Clerk's fail-closed middleware.
export default localOnly ? localOnlyMiddleware : clerkMiddleware();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};
