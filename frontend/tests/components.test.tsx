import { render, screen } from "@testing-library/react";
import { TrendingUp } from "lucide-react";
import { describe, expect, it } from "vitest";

import { ApiUnavailable, EmptyState } from "@/components/dashboard/data-states";
import { MetricCard } from "@/components/dashboard/metric-card";
import { SignalBadge } from "@/components/dashboard/signal-badge";

describe("dashboard presentation components", () => {
  it("renders an evidence-backed metric without transforming it", () => {
    render(
      <MetricCard
        label="Current prediction"
        value="2.308%"
        detail="5-observation forward log return"
        icon={TrendingUp}
      />,
    );

    expect(screen.getByText("Current prediction")).toBeInTheDocument();
    expect(screen.getByText("2.308%")).toBeInTheDocument();
    expect(
      screen.getByText("5-observation forward log return"),
    ).toBeInTheDocument();
  });

  it.each(["BUY", "HOLD", "EXIT"] as const)(
    "renders the %s signal exactly",
    (action) => {
      render(<SignalBadge action={action} />);
      expect(screen.getByText(action)).toBeInTheDocument();
    },
  );

  it("makes unavailable data explicit", () => {
    render(<ApiUnavailable message="Connection refused." />);
    expect(
      screen.getByText("Live Prediction API unavailable"),
    ).toBeInTheDocument();
    expect(screen.getByText("Connection refused.")).toBeInTheDocument();
  });

  it("renders an honest empty state", () => {
    render(
      <EmptyState
        title="No closed trades"
        description="No immutable trade evidence is available."
      />,
    );
    expect(screen.getByText("No closed trades")).toBeInTheDocument();
  });
});
