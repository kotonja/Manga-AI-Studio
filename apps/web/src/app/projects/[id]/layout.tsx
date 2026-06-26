import type { ReactNode } from "react";

import { ProjectFrame } from "@/components/layout/project-frame";

export default async function ProjectLayout({
  children,
  params
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProjectFrame projectId={id}>{children}</ProjectFrame>;
}
