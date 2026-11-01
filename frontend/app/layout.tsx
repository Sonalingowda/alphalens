import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/dashboard/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ClerkProvider } from "@clerk/nextjs";

const localOnly = process.env.ALPHALENS_LOCAL_ONLY === "true";

export const metadata: Metadata = {
  title: {
    default: "AlphaLens",
    template: "%s · AlphaLens",
  },
  description:
    "Deterministic, explainable market opportunity intelligence.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="dark font-sans"
      suppressHydrationWarning
    >
      <body>
        {localOnly ? (
          <TooltipProvider>
            <AppShell>{children}</AppShell>
          </TooltipProvider>
        ) : (
          <ClerkProvider>
            <TooltipProvider>
              <AppShell>{children}</AppShell>
            </TooltipProvider>
          </ClerkProvider>
        )}
      </body>
    </html>
  );
}
