"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type Props = { opportunityId: string; asOf?: string; direction: string };

export function EconomicAnalysis({ opportunityId, asOf, direction }: Props) {
  const [currency, setCurrency] = useState("INR");
  const [notional, setNotional] = useState("500");
  const [fx, setFx] = useState("");
  const [fee, setFee] = useState("10");
  const [slippage, setSlippage] = useState("5");
  const [semantics, setSemantics] = useState(direction === "SELL" ? "spot" : "spot");
  const [result, setResult] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function calculate() {
    setError(null);
    const params = new URLSearchParams({
      position_notional: notional,
      currency,
      entry_fee_bps: fee,
      exit_fee_bps: fee,
      entry_slippage_bps: slippage,
      exit_slippage_bps: slippage,
      instrument_semantics: semantics,
    });
    if (fx.trim()) params.set("fx_to_usd", fx.trim());
    if (asOf) params.set("as_of", asOf);
    const base = (process.env.NEXT_PUBLIC_ALPHALENS_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
    try {
      const response = await fetch(`${base}/api/v1/opportunities/${encodeURIComponent(opportunityId)}/economics?${params}`, { cache: "no-store" });
      const envelope = await response.json() as { data?: { analysis?: Record<string, string> } };
      if (!response.ok || !envelope.data?.analysis) throw new Error("Economic analysis unavailable.");
      setResult(envelope.data.analysis);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Economic analysis unavailable.");
    }
  }

  return (
    <Card className="bg-card/95">
      <CardHeader>
        <CardTitle>Economic analysis</CardTitle>
        <CardDescription>
          Deterministic arithmetic under your explicit assumptions. This is not expected value, probability, or a profit promise.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-xs text-muted-foreground">Currency<select className="mt-1 w-full rounded border bg-background p-2 text-foreground" value={currency} onChange={(event) => setCurrency(event.target.value)}><option>INR</option><option>USD</option></select></label>
          <label className="text-xs text-muted-foreground">Position notional<input className="mt-1 w-full rounded border bg-background p-2 text-foreground" value={notional} onChange={(event) => setNotional(event.target.value)} inputMode="decimal" /></label>
          <label className="text-xs text-muted-foreground">INR → USD rate<input className="mt-1 w-full rounded border bg-background p-2 text-foreground" value={fx} onChange={(event) => setFx(event.target.value)} placeholder="Required for INR" inputMode="decimal" /></label>
          <label className="text-xs text-muted-foreground">Fee (bps each side)<input className="mt-1 w-full rounded border bg-background p-2 text-foreground" value={fee} onChange={(event) => setFee(event.target.value)} inputMode="decimal" /></label>
          <label className="text-xs text-muted-foreground">Slippage (bps each side)<input className="mt-1 w-full rounded border bg-background p-2 text-foreground" value={slippage} onChange={(event) => setSlippage(event.target.value)} inputMode="decimal" /></label>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-xs text-muted-foreground">Instrument semantics<select className="ml-2 rounded border bg-background p-2 text-foreground" value={semantics} onChange={(event) => setSemantics(event.target.value)}><option value="spot">Spot</option><option value="perpetual_derivative">Explicit short-capable derivative</option></select></label>
          <Button type="button" onClick={calculate}>Calculate scenario</Button>
          <Badge variant="outline">Model output unavailable</Badge>
        </div>
        {error ? <p className="text-sm text-amber-300">{error}</p> : null}
        {result ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Status" value={result.status ?? "Unavailable"} />
            <Metric label="Gross target profit" value={result.gross_potential_profit ?? "Unavailable"} />
            <Metric label="Modeled costs" value={result.total_modeled_costs ?? "Unavailable"} />
            <Metric label="Net target profit" value={result.estimated_net_target_profit ?? "Unavailable"} />
            <Metric label="Net stop loss" value={result.estimated_net_stop_loss ?? "Unavailable"} />
            <Metric label="Net risk / reward" value={result.estimated_net_risk_reward ?? "Unavailable"} />
            <Metric label="Break-even movement" value={result.break_even_movement_fraction ?? "Unavailable"} />
            <Metric label="Reason" value={result.reason ?? "Explicit assumptions applied"} />
          </div>
        ) : <p className="text-sm text-muted-foreground">No scenario calculated. INR requires an explicitly entered conversion rate; SELL requires short-capable instrument semantics.</p>}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border bg-muted/20 p-3"><p className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">{label}</p><p className="mt-1 break-words font-mono text-xs">{value}</p></div>;
}
