import { clerkMiddleware } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const localDemoMode = process.env.ALPHALENS_LOCAL_DEMO_MODE === "true";

// The local historical replay has no Clerk secret and must remain explicitly
// unauthenticated. Production and non-demo environments retain Clerk's
// fail-closed middleware.
export default localDemoMode
  ? () => NextResponse.next()
  : clerkMiddleware();

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/(.*)",
  ],
};
