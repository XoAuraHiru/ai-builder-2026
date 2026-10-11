"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/investor", label: "Investor" },
  { href: "/advisor", label: "Advisor" },
  { href: "/operations", label: "Operations" },
  { href: "/compliance", label: "Compliance" },
];

export function Nav() {
  const path = usePathname();
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-tight text-[#0b5fff]">
          Atrium
        </Link>
        <nav className="flex flex-wrap gap-4 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={path.startsWith(l.href) ? "font-semibold text-slate-900" : "text-slate-500"}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <Link href="/apply" className="ml-auto text-sm text-slate-500">
          Prospect form
        </Link>
        <Link href="/login" className="text-sm text-slate-500">
          Switch user
        </Link>
      </div>
    </header>
  );
}
