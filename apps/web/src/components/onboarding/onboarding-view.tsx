"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, Clapperboard, KeyRound, ShieldCheck, Sparkles } from "lucide-react";
import type { AlphaOnboardingInfo } from "@manga-ai/shared";

import { apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function OnboardingView() {
  const router = useRouter();
  const search = useSearchParams();
  const [info, setInfo] = useState<AlphaOnboardingInfo | null>(null);
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const nextPath = search.get("next") || "/";
  const authEnabled = Boolean(info?.auth.auth_enabled);

  useEffect(() => {
    let cancelled = false;
    apiFetch<AlphaOnboardingInfo>("/alpha/onboarding")
      .then((payload) => {
        if (!cancelled) {
          setInfo(payload);
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load onboarding");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const providerModes = useMemo(() => info?.provider_modes ?? [], [info]);

  async function login() {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/alpha-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      router.push(nextPath);
      router.refresh();
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to unlock alpha");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[linear-gradient(135deg,#101014,#25251f_42%,#f4efe2)] px-4 py-8 text-white sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="grid min-h-[420px] items-end rounded-md border border-white/15 bg-[radial-gradient(circle_at_18%_12%,rgba(255,255,255,0.22),transparent_22rem),linear-gradient(180deg,rgba(0,0,0,0.1),rgba(0,0,0,0.56))] p-6 shadow-2xl">
          <div className="max-w-3xl">
            <Badge className="border-white/20 bg-white/12 text-white">Private Alpha</Badge>
            <h1 className="mt-5 text-4xl font-semibold tracking-normal sm:text-5xl">{info?.welcome_title ?? "Welcome to Manga AI Studio Alpha"}</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-white/78">{info?.welcome_message ?? "Loading alpha guide..."}</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild className="bg-white text-black hover:bg-white/90">
                <Link href="/demo">
                  <Clapperboard className="h-4 w-4" />
                  Founder Demo
                </Link>
              </Button>
              <Button asChild variant="outline" className="border-white/30 bg-white/10 text-white hover:bg-white/16">
                <Link href="/">
                  <Sparkles className="h-4 w-4" />
                  Open Studio
                </Link>
              </Button>
            </div>
          </div>
        </header>

        {error ? <div className="rounded-md border border-red-300/30 bg-red-500/15 px-4 py-3 text-sm text-red-50">{error}</div> : null}

        <section className="grid gap-4 lg:grid-cols-[360px_1fr]">
          <Card className="border-white/15 bg-white/94 text-foreground">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <KeyRound className="h-5 w-5" />
                Alpha Access
              </CardTitle>
              <CardDescription>{authEnabled ? "Enter the tester password from your invite." : "Local auth is disabled for development."}</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <Input
                type="password"
                placeholder={authEnabled ? "Alpha password" : "No password needed locally"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={!authEnabled}
              />
              <Button onClick={() => void login()} disabled={isSubmitting || (authEnabled && !password.trim())}>
                <ShieldCheck className="h-4 w-4" />
                {authEnabled ? "Unlock Studio" : "Continue"}
              </Button>
              <p className="text-xs text-muted-foreground">
                Production deployments should connect a real auth provider or trusted reverse-proxy auth header.
              </p>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            {providerModes.map((mode) => (
              <Card key={String(mode.id)} className="border-white/15 bg-white/94 text-foreground">
                <CardHeader>
                  <CardTitle>{String(mode.name)}</CardTitle>
                  <CardDescription>Cost risk: {String(mode.cost_risk)}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">{String(mode.description)}</CardContent>
              </Card>
            ))}
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <Card className="border-white/15 bg-white/94 text-foreground">
            <CardHeader>
              <CardTitle>First Steps</CardTitle>
              <CardDescription>Best path for a useful alpha session</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(info?.suggested_first_steps ?? []).map((step) => (
                <div key={step} className="flex gap-3 text-sm">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>{step}</span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-white/15 bg-white/94 text-foreground">
            <CardHeader>
              <CardTitle>Safety and Rights</CardTitle>
              <CardDescription>Rules testers should follow</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {(info?.safety_rules ?? []).map((rule) => (
                <div key={rule} className="flex gap-3 text-sm">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <span>{rule}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
