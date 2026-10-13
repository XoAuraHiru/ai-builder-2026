import { ButtonLink, EmptyState } from "@/components/ui";

/** Any address Atrium does not have: said plainly, with a way back, in Atrium's own design. */
export default function NotFound() {
  return (
    <div className="mx-auto max-w-[640px] py-10">
      <EmptyState title="This page isn't here"
        action={<ButtonLink href="/" variant="tonal">Back to the front door</ButtonLink>}>
        The address may be mistyped, or the page has moved. Every workspace starts from its rail on the left.
      </EmptyState>
    </div>
  );
}
