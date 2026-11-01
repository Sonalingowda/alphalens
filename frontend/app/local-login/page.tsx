import Link from "next/link";

export default async function LocalLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; next?: string }>;
}) {
  const params = await searchParams;
  const next = params.next?.startsWith("/") && !params.next.startsWith("//") ? params.next : "/";
  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-6">
      <section className="w-full space-y-5 rounded-xl border border-border bg-card p-6">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-primary">Local owner access</p>
          <h1 className="mt-2 text-2xl font-semibold">Sign in to AlphaLens</h1>
          <p className="mt-2 text-sm text-muted-foreground">This access path is available only from the owner’s loopback machine.</p>
        </div>
        {params.error ? <p className="text-sm text-rose-400">The local access token was not accepted.</p> : null}
        <form method="post" action="/api/local-auth/login" className="space-y-4">
          <input type="hidden" name="next" value={next} />
          <label className="block text-sm">
            Local access token
            <input name="token" type="password" autoComplete="current-password" required className="mt-2 h-10 w-full rounded-md border bg-background px-3" />
          </label>
          <button type="submit" className="h-10 w-full rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">Continue</button>
        </form>
        <Link href="/" className="text-xs text-muted-foreground underline">Return to dashboard</Link>
      </section>
    </main>
  );
}
