import { DirectorModeView } from "@/components/director/director-mode-view";

export default async function DirectorModePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DirectorModeView projectId={id} />;
}
