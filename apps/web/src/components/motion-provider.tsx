"use client";

import { MotionConfig } from "motion/react";

/** One place for motion defaults. reducedMotion="user" turns movement off for people who ask their OS for that. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user" transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}>
      {children}
    </MotionConfig>
  );
}
