import { Notice, PageHeader } from "@/components/ui";

export function WorkspacePlaceholder({ name, arrives }: { name: string; arrives: string }) {
  return (
    <>
      <PageHeader title={`${name} workspace`} description={arrives} />
      <Notice title="Arriving in the Operate release">
        This workspace is next in the build plan. The investor and advisor workspaces are complete today.
      </Notice>
    </>
  );
}
