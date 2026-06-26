import { QARoomView } from "@/components/qa/qa-room-view";

export default async function QARoomPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <QARoomView projectId={id} />;
}
