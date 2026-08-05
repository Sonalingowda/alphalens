import React from "react";
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { OpportunityFilters } from "@/components/opportunities/opportunity-filters";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";

describe("Accessibility: decorative icons and labels", () => {
  it("marks search icon as aria-hidden in OpportunityFilters", () => {
    const { container } = render(
      <OpportunityFilters values={{ search: "", timeframe: "5m", stance: undefined, instrument: "" }} />
    );
    const searchIcon = container.querySelector('svg.lucide-search, svg[aria-hidden]');
    expect(searchIcon).toBeTruthy();
    if (searchIcon) expect(searchIcon).toHaveAttribute("aria-hidden", "true");
  });

  it("marks decorative icons in OpportunityCard as aria-hidden", () => {
    const item = {
      opportunity_id: "1",
      opportunity_version_id: "v1",
      scope: { instrument: "AAPL", timeframe: "5m" },
      rank: 1,
      lifecycle_state: "active",
      stance: "BUY" as const,
      reason_codes: [],
      available_at: "2026-08-02T20:24:00Z",
      freshness_state: "fresh",
      evidence_cutoff: "2026-08-01T00:00:00Z",
      has_plan: false,
      detail_reference: "",
      limitations: [],
    };
    const { container } = render(<OpportunityCard item={item} />);
    const icons = Array.from(container.querySelectorAll('svg[aria-hidden="true"]'));
    expect(icons.length).toBeGreaterThan(0);
    icons.forEach((icon) => expect(icon).toHaveAttribute("aria-hidden", "true"));
  });
});
