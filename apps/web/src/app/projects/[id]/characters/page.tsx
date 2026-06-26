import { CharacterLabView } from "@/components/labs/character-lab-view";

export default async function CharacterLabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CharacterLabView projectId={id} />;
}
