import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DashboardLoading from "@/app/loading";
import MarketsLoading from "@/app/markets/loading";
import OpportunityLoading from "@/app/opportunities/[id]/loading";

describe("route loading boundaries", () => {
  it("renders dashboard loading skeletons", () => {
    const { container } = render(<DashboardLoading />);
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });

  it("renders markets loading skeletons", () => {
    const { container } = render(<MarketsLoading />);
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });

  it("renders opportunity detail loading skeletons", () => {
    const { container } = render(<OpportunityLoading />);
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
  });
});
