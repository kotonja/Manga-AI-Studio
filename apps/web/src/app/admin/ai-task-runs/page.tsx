import { notFound } from "next/navigation";

import { AITaskRunsAdminView } from "@/components/admin/ai-task-runs-admin-view";

export const dynamic = "force-dynamic";

export default function AITaskRunsAdminPage() {
  if (!isDevAdminEnabled()) {
    notFound();
  }
  return <AITaskRunsAdminView />;
}

function isDevAdminEnabled() {
  return (
    process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "true" ||
    process.env.ENABLE_DEV_ADMIN === "true" ||
    process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_ENABLE_DEV_ADMIN === "local"
  );
}
