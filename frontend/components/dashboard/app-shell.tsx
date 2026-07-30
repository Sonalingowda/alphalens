"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import {
  Activity,
  BarChart3,
  FlaskConical,
  HeartPulse,
  History,
  LayoutDashboard,
  Menu,
  Radio,
  Settings,
  ShieldAlert,
  WalletCards,
} from "lucide-react";

import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/predictions", label: "Predictions", icon: Activity },
  { href: "/paper-trading", label: "Paper Trading", icon: Radio },
  { href: "/portfolio", label: "Portfolio", icon: WalletCards },
  { href: "/trade-history", label: "Trade History", icon: History },
  { href: "/risk-events", label: "Risk Events", icon: ShieldAlert },
  { href: "/backtest-reports", label: "Backtest Reports", icon: FlaskConical },
  { href: "/system-health", label: "System Health", icon: HeartPulse },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-3" aria-label="AlphaLens">
      <span className="grid size-9 place-items-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
        <BarChart3 className="size-5" aria-hidden="true" />
      </span>
      <span>
        <span className="block text-sm font-semibold tracking-[0.12em]">
          ALPHALENS
        </span>
        <span className="block text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
          Research Operations
        </span>
      </span>
    </Link>
  );
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="space-y-1" aria-label="Primary navigation">
      {navigation.map((item) => {
        const active =
          item.href === "/"
            ? pathname === "/"
            : pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex min-h-10 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
              active
                ? "bg-primary/12 text-primary ring-1 ring-primary/20"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r bg-sidebar lg:flex lg:flex-col">
        <div className="border-b p-5">
          <Brand />
        </div>
        <div className="flex-1 p-3">
          <Navigation />
        </div>
        <div className="border-t p-4 text-xs text-muted-foreground">
          <div className="mb-1 flex items-center gap-2 text-foreground">
            <span className="size-1.5 rounded-full bg-emerald-400" />
            Artifact-only inference
          </div>
          No training surface
        </div>
      </aside>

      <div className="min-w-0 lg:col-start-2">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-3 lg:hidden">
            <Sheet>
              <SheetTrigger
                render={
                  <Button variant="outline" size="icon" aria-label="Open menu" />
                }
              >
                <Menu className="size-4" />
              </SheetTrigger>
              <SheetContent side="left" className="w-[280px]">
                <SheetHeader className="border-b p-5">
                  <SheetTitle className="sr-only">Navigation</SheetTitle>
                  <SheetDescription className="sr-only">
                    AlphaLens dashboard navigation
                  </SheetDescription>
                  <Brand />
                </SheetHeader>
                <div className="p-3">
                  <Navigation />
                </div>
              </SheetContent>
            </Sheet>
            <Brand />
          </div>
          <div className="hidden items-center gap-2 text-xs uppercase tracking-[0.16em] text-muted-foreground lg:flex">
            <span className="size-1.5 rounded-full bg-emerald-400" />
            Operational console
          </div>
          <ThemeToggle />
        </header>
        <main className="dashboard-grid min-h-[calc(100vh-4rem)] p-4 md:p-6 xl:p-8">
          <div className="mx-auto max-w-[1600px]">{children}</div>
        </main>
      </div>
    </div>
  );
}
