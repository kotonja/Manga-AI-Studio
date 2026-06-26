import { ProjectProvenanceView } from "@/components/provenance/project-provenance-view";

export default async function ProjectProvenancePage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ProjectProvenanceView projectId={id} />;
}
