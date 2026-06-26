import { PublishingRoomView } from "@/components/publishing/publishing-room-view";

export default async function PublishingRoomPage({
  params
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <PublishingRoomView projectId={id} />;
}
