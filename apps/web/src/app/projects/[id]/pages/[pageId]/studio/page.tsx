import { PageStudioView } from "@/components/page-studio/page-studio-view";

export default async function PageStudioPage({
  params
}: {
  params: Promise<{ id: string; pageId: string }>;
}) {
  const { id, pageId } = await params;
  return <PageStudioView projectId={id} pageId={pageId} />;
}
