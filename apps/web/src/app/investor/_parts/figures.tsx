"use client";

import { CountUp } from "@/components/motion";
import { splitSign } from "@/lib/invest";

/** A signed engine figure that counts up to itself: "−$7,420" counts as it is; "+$1,240" keeps its plus still and
 *  counts the rest, since the counter reads a minus sign but not a plus. */
export function SignedCount({ text, className = "" }: { text: string; className?: string }) {
  const { sign, figure } = splitSign(text);
  return <span className={className}>{sign}<CountUp text={figure} /></span>;
}
