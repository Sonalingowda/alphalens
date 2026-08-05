import { Filter, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { OpportunityFilters as FilterValues } from "@/lib/types";

export function OpportunityFilters({ values }: { values: FilterValues }) {
  return (
    <form
      method="get"
      className="grid gap-3 rounded-xl border bg-card/90 p-3 sm:grid-cols-[minmax(180px,1fr)_120px_120px_auto]"
      aria-label="Opportunity filters"
    >
      <label className="relative">
        <span className="sr-only">Search opportunities</span>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
        <input
          name="search"
          defaultValue={values.search}
          placeholder="Search symbol or evidence"
          className="h-10 w-full rounded-md border bg-background/70 pl-9 pr-3 text-sm outline-none transition focus:border-primary/60 focus:ring-2 focus:ring-primary/15"
        />
      </label>
      <label>
        <span className="sr-only">Timeframe</span>
        <select
          name="timeframe"
          defaultValue={values.timeframe}
          className="h-10 w-full rounded-md border bg-background/70 px-3 text-sm outline-none focus:border-primary/60"
        >
          <option value="5m">5 minutes</option>
          <option value="10m">10 minutes</option>
          <option value="15m">15 minutes</option>
        </select>
      </label>
      <label>
        <span className="sr-only">Direction</span>
        <select
          name="stance"
          defaultValue={values.stance ?? ""}
          className="h-10 w-full rounded-md border bg-background/70 px-3 text-sm outline-none focus:border-primary/60"
        >
          <option value="">All directions</option>
          <option value="BUY">Buy</option>
          <option value="SELL">Sell</option>
        </select>
      </label>
      <input type="hidden" name="instrument" value={values.instrument} />
      <Button type="submit" className="h-10 gap-2">
        <Filter className="size-4" />
        Apply
      </Button>
    </form>
  );
}
