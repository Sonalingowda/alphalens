import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export function SignalBadge({
  action,
  className,
}: {
  action: "BUY" | "HOLD" | "EXIT" | null;
  className?: string;
}) {
  const value = action ?? "UNAVAILABLE";
  return (
    <Badge
      variant="outline"
      className={cn(
        "tabular font-medium tracking-[0.12em]",
        action === "BUY" &&
          "border-emerald-400/30 bg-emerald-400/10 text-emerald-400",
        action === "EXIT" &&
          "border-rose-400/30 bg-rose-400/10 text-rose-400",
        action === "HOLD" &&
          "border-amber-400/30 bg-amber-400/10 text-amber-300",
        !action && "text-muted-foreground",
        className,
      )}
    >
      {value}
    </Badge>
  );
}
