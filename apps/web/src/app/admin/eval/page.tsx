import { notFound } from "next/navigation";

import { EvalHarnessAdminView } from "@/components/admin/eval-harness-admin-view";

export const dynamic = "force-dynamic";

export default function EvalHarnessAdminPage() {
  if (!isDevAdminEnabled()) {
    notFound();
  }
  return <EvalHarnessAdminView />;
}

function isDevAdminEnabled() {
  return (
    process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "true" ||
    process.env.ENABLE_DEV_ADMIN === "true" ||
    (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "local")
  );
}
