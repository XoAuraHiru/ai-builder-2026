import type { ReactNode } from "react";
import type { IconName } from "@/lib/nav";

const PATHS: Record<IconName, ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  portfolio: <><path d="M21 12A9 9 0 1 1 12 3v9z" /><path d="M15 3.5A9 9 0 0 1 20.5 9H15z" /></>,
  markets: <><path d="m3 17 6-6 4 4 8-8" /><path d="M14 7h7v7" /></>,
  funds: <><path d="m12 3 9 4.5-9 4.5-9-4.5z" /><path d="m3 12 9 4.5 9-4.5" /><path d="m3 16.5 9 4.5 9-4.5" /></>,
  plan: <><path d="M3 3v18h18" /><path d="M7 15c3-1 7-4 13-9" /><path d="M7 15c4 0 8-1 13-3" strokeDasharray="2 2.5" /></>,
  leads: <path d="M4 5h16l-6 7v6l-4 2v-8z" />,
  held: <><rect x="5" y="4" width="14" height="16" rx="2" /><path d="M9 9h6M9 13h6" /></>,
  form: <><rect x="5" y="4" width="14" height="16" rx="2" /><path d="M12 9v6M9 12h6" /></>,
  today: <><circle cx="12" cy="12" r="4" /><path d="M12 3v2M12 19v2M3 12h2M19 12h2" /></>,
  reconcile: <path d="M5 8h10l-3-3M19 16H9l3 3" />,
  approvals: <path d="M5 12l4 4 10-10" />,
  blotter: <path d="M5 6h14M5 12h14M5 18h9" />,
  alerts: <><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17v.5" /></>,
  log: <><rect x="5" y="4" width="14" height="16" rx="2" /><path d="M9 9h6M9 13h6M9 17h3" /></>,
  models: <><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" /><path d="M9 12l2 2 4-4" /></>,
  rings: <><circle cx="6" cy="17" r="2.5" /><circle cx="18" cy="17" r="2.5" /><circle cx="12" cy="6" r="2.5" /><path d="M8.5 17h7M7.3 14.8l3.4-6.4M16.7 14.8l-3.4-6.4" /></>,
};

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
