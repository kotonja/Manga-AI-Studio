import { WorldRoomView } from "@/components/world/world-room-view";

export default async function WorldRoomPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <WorldRoomView projectId={id} />;
}
