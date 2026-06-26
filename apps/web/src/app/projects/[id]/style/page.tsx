import { StyleLabView } from "@/components/labs/style-lab-view";

export default async function StyleLabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StyleLabView projectId={id} />;
}
