import { notFound } from "next/navigation";

import { AlphaReadinessView } from "@/components/admin/alpha-readiness-view";
import { isAdminAccessAllowed } from "@/lib/admin-access";

export const dynamic = "force-dynamic";

export default async function AlphaReadinessPage() {
  if (!(await isAdminAccessAllowed())) {
    notFound();
  }
  return <AlphaReadinessView />;
}
