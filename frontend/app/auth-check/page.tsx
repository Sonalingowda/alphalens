"use client";

import { SignInButton, useAuth } from "@clerk/nextjs";
import { useState } from "react";

import { PageHeader } from "@/components/dashboard/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { checkProtectedSession } from "@/lib/api-client";

type CheckState =
  | { kind: "idle" }
  | { kind: "checking" }
  | {
      kind: "result";
      status: number;
      errorCode: string | null;
      authorization: string;
      checkedAt: string;
    }
  | { kind: "error"; message: string };

export default function AuthCheckPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [state, setState] = useState<CheckState>({ kind: "idle" });

  async function checkSession() {
    setState({ kind: "checking" });
    try {
      const token = await getToken();
      if (!token) {
        setState({
          kind: "result",
          status: 401,
          errorCode: "HTTP_ERROR",
          authorization: "unauthenticated",
          checkedAt: new Date().toISOString(),
        });
        return;
      }
      const result = await checkProtectedSession(token);
      setState({
        kind: "result",
        status: result.status,
        errorCode: result.errorCode,
        authorization: result.authorization,
        checkedAt: new Date().toISOString(),
      });
    } catch (error) {
      setState({
        kind: "error",
        message: error instanceof Error ? error.message : "The API request failed.",
      });
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Owner verification"
        title="Clerk API session check"
        description="Sends one read-only request through the existing paper-tracking authorization boundary. The sentinel reference is never persisted."
      />
      <Card className="max-w-2xl bg-card/95">
        <CardHeader>
          <CardTitle>Authenticated browser request</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {!isLoaded ? <p className="text-sm text-muted-foreground">Loading Clerk session…</p> : null}
          {isLoaded && !isSignedIn ? (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Sign in with the authorized Clerk Development user first.</p>
              <SignInButton mode="modal">
                <Button variant="outline">Sign in</Button>
              </SignInButton>
            </div>
          ) : null}
          {isLoaded && isSignedIn ? (
            <Button onClick={checkSession} disabled={state.kind === "checking"}>
              {state.kind === "checking" ? "Checking API authorization…" : "Check protected API"}
            </Button>
          ) : null}
          {state.kind === "result" ? (
            <dl className="grid gap-2 rounded-md border p-4 text-sm sm:grid-cols-3">
              <div><dt className="text-muted-foreground">Endpoint category</dt><dd>Protected read-only</dd></div>
              <div><dt className="text-muted-foreground">HTTP status</dt><dd>{state.status}</dd></div>
              <div><dt className="text-muted-foreground">Application code</dt><dd>{state.errorCode ?? "none"}</dd></div>
              <div><dt className="text-muted-foreground">Authorization</dt><dd>{state.authorization}</dd></div>
              <div className="sm:col-span-3"><dt className="text-muted-foreground">Checked at</dt><dd>{state.checkedAt}</dd></div>
            </dl>
          ) : null}
          {state.kind === "error" ? <p className="text-sm text-rose-400">{state.message}</p> : null}
          <p className="text-xs text-muted-foreground">
            Expected authorized result: HTTP 404 with application code “entity.not_found”, because no sentinel opportunity exists. Expected unauthenticated result: HTTP 401. A status alone never proves authorization.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
