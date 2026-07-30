import { AlertTriangle, Inbox } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

export function ApiUnavailable({ message }: { message: string }) {
  return (
    <Card className="border-amber-500/25 bg-amber-500/5">
      <CardContent className="flex min-h-52 flex-col items-center justify-center text-center">
        <AlertTriangle className="mb-4 size-7 text-amber-400" />
        <h2 className="font-medium">Live Prediction API unavailable</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">{message}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Start the API and refresh this page. No placeholder values are shown.
        </p>
      </CardContent>
    </Card>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-lg border border-dashed p-6 text-center">
      <Inbox className="mb-3 size-6 text-muted-foreground" />
      <p className="text-sm font-medium">{title}</p>
      <p className="mt-1 max-w-lg text-xs leading-5 text-muted-foreground">
        {description}
      </p>
    </div>
  );
}
