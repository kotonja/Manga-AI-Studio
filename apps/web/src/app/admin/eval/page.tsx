import { notFound } from "next/navigation";

import { EvalHarnessAdminView } from "@/components/admin/eval-harness-admin-view";
import { isAdminAccessAllowed } from "@/lib/admin-access";

export const dynamic = "force-dynamic";

export default async function EvalHarnessAdminPage() {
  if (!(await isAdminAccessAllowed())) {
    notFound();
  }
  return <EvalHarnessAdminView />;
}
