"use client";

import { useAuth, SignInButton } from "@clerk/nextjs";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  confirmPaperTracking,
  selectPaperTracking,
} from "@/lib/api-client";

export function PaperTrackControl({
  opportunityId,
  opportunityVersionId,
}: {
  opportunityId: string;
  opportunityVersionId: string;
}) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [state, setState] = useState<"idle" | "working" | "active" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);

  if (!isLoaded) {
    return <Button disabled>Checking session…</Button>;
  }
  if (!isSignedIn) {
    return (
      <SignInButton mode="modal">
        <Button variant="outline">Sign in to paper track</Button>
      </SignInButton>
    );
  }

  async function select() {
    setState("working");
    setMessage(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("A valid Clerk session is required.");
      const confirmation = await confirmPaperTracking(
        token,
        opportunityId,
        opportunityVersionId,
      );
      const result = await selectPaperTracking(token, confirmation);
      setState("active");
      setMessage(`Active paper track: ${result.execution_id}`);
    } catch (error) {
      setState("error");
      setMessage(error instanceof Error ? error.message : "Paper tracking failed.");
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button onClick={select} disabled={state === "working" || state === "active"}>
        {state === "working" ? "Confirming…" : state === "active" ? "Paper track active" : "Confirm paper track"}
      </Button>
      {message ? (
        <span className={state === "error" ? "text-sm text-rose-400" : "text-sm text-emerald-400"}>
          {message}
        </span>
      ) : null}
    </div>
  );
}
