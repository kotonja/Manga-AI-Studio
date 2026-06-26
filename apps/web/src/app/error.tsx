"use client";

import { useEffect, useMemo } from "react";
import Link from "next/link";
import { AlertTriangle, Clipboard, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const diagnostic = useMemo(
    () =>
      JSON.stringify(
        {
          message: error.message,
          digest: error.digest,
          timestamp: new Date().toISOString(),
          pathname: typeof window !== "undefined" ? window.location.pathname : ""
        },
        null,
        2
      ),
    [error]
  );

  async function copyDiagnostic() {
    await navigator.clipboard.writeText(diagnostic);
  }

  return (
    <main className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-xl rounded-md border bg-white p-6 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-destructive/10 text-destructive">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Something needs attention</h1>
            <p className="text-sm text-muted-foreground">The app caught an error without exposing private logs.</p>
          </div>
        </div>
        <pre className="mt-4 max-h-48 overflow-auto rounded-md bg-muted/70 p-3 text-xs text-muted-foreground">{diagnostic}</pre>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={reset}>
            <RefreshCcw className="h-4 w-4" />
            Try again
          </Button>
          <Button variant="outline" onClick={() => void copyDiagnostic()}>
            <Clipboard className="h-4 w-4" />
            Copy diagnostic info
          </Button>
          <Button asChild variant="ghost">
            <Link href="/">Dashboard</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
