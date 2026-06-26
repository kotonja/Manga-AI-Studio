import { Suspense } from "react";

import { OnboardingView } from "@/components/onboarding/onboarding-view";

export default function OnboardingPage() {
  return (
    <Suspense fallback={<main className="grid min-h-screen place-items-center text-sm text-muted-foreground">Loading onboarding</main>}>
      <OnboardingView />
    </Suspense>
  );
}
