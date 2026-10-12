type ValidationIssue = { loc?: (string | number)[]; msg?: string };

/** FastAPI sends either a sentence or a list of validation issues; people should always get a sentence. */
export function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) {
    const parts = (detail as ValidationIssue[])
      .filter((d) => d && typeof d.msg === "string")
      .map((d) => {
        const field = (d.loc ?? []).filter((x) => x !== "body").join(" ").replaceAll("_", " ");
        const msg = d.msg!.charAt(0).toLowerCase() + d.msg!.slice(1);
        return field ? `${field} (${msg})` : msg;
      });
    if (parts.length) return `Check these fields: ${parts.join("; ")}.`;
  }
  return fallback;
}
