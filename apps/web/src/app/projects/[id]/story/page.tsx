import { StoryRoomView } from "@/components/story/story-room-view";

export default async function StoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StoryRoomView projectId={id} />;
}
