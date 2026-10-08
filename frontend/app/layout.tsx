import type { Metadata } from "next";
import "./globals.css";
import { Geist } from "next/font/google";
import { AppShell } from "@/components/dashboard/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { ClerkProvider } from "@clerk/nextjs";

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" });

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
      className={cn("dark font-sans", geist.variable)}
      suppressHydrationWarning
    >
      <body>
        <ClerkProvider>
          <TooltipProvider>
            <AppShell>{children}</AppShell>
          </TooltipProvider>
        </ClerkProvider>
      </body>
    </html>
  );
}
