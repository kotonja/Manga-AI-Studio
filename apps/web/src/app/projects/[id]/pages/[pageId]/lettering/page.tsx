import { LetteringRoomView } from "@/components/lettering/lettering-room-view";

export default async function LetteringRoomPage({
  params
}: {
  params: Promise<{ id: string; pageId: string }>;
}) {
  const { id, pageId } = await params;
  return <LetteringRoomView projectId={id} pageId={pageId} />;
}
