import type { ReactNode } from "react";
import type { IconName } from "@/lib/nav";

const PATHS: Record<IconName, ReactNode> = {
  home: <path d="M4 11 12 4l8 7v9H4z" />,
  portfolio: <><circle cx="12" cy="12" r="8" /><path d="M12 4v8l6 4" /></>,
  markets: <><path d="M4 17l5-5 4 3 7-8" /><path d="M15 7h5v5" /></>,
  funds: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M9 4v16M4 10h5" /></>,
  plan: <><path d="M4 18c4-1 6-5 8-9s5-5 8-5" /><path d="M4 21h16" /></>,
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
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
