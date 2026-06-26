import { notFound } from "next/navigation";

import { AITaskRunsAdminView } from "@/components/admin/ai-task-runs-admin-view";
import { isAdminAccessAllowed } from "@/lib/admin-access";

export const dynamic = "force-dynamic";

export default async function AITaskRunsAdminPage() {
  if (!(await isAdminAccessAllowed())) {
    notFound();
  }
  return <AITaskRunsAdminView />;
}
