"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, RefreshCcw, ShieldCheck } from "lucide-react";
import type { AlphaReadiness } from "@manga-ai/shared";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

export function AlphaReadinessView() {
  const [readiness, setReadiness] = useState<AlphaReadiness | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadReadiness() {
    setIsLoading(true);
    setError(null);
    try {
      setReadiness(await apiFetch<AlphaReadiness>("/alpha/readiness"));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load alpha readiness");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadReadiness();
  }, []);

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-5xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-3">
            <Button asChild variant="ghost" size="sm" className="w-fit">
              <Link href="/admin/alpha">
                <ArrowLeft className="h-4 w-4" />
                Alpha Dashboard
              </Link>
            </Button>
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-3xl font-semibold tracking-normal">Alpha Readiness</h1>
                <Badge className={readiness?.ready ? "" : "border-destructive/40 bg-destructive/10 text-destructive"}>{readiness?.ready ? "Ready" : "Needs attention"}</Badge>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">Admin-only launch checks for auth, storage, worker, and provider setup.</p>
            </div>
          </div>
          <Button variant="outline" onClick={() => void loadReadiness()} disabled={isLoading}>
            <RefreshCcw className="h-4 w-4" />
            Refresh
          </Button>
        </header>

        {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</div> : null}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5" />
              Launch Checklist
            </CardTitle>
            <CardDescription>Failures should be fixed before inviting controlled alpha testers.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading && !readiness ? <div className="h-24 animate-pulse rounded-md border bg-muted/40" /> : null}
            {(readiness?.checks ?? []).map((check) => (
              <div key={check.name} className="flex flex-col gap-2 rounded-md border bg-white p-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-medium capitalize">{check.name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{check.message}</p>
                </div>
                <Badge className={check.status === "fail" ? "border-destructive/40 bg-destructive/10 text-destructive" : check.status === "warn" ? "bg-muted" : ""}>{check.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
