import type { Metadata } from "next";
import { Geist_Mono, Newsreader, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";
import { MotionProvider } from "@/components/motion-provider";
import { Shell } from "@/components/shell";
import { SessionProvider } from "@/lib/session-context";

// Design system 0.2: three voices. Schibsted Grotesk for the interface and engine figures, Newsreader for anything
// Gemini writes, Geist Mono for IDs, codes, model names and cost.
const grotesk = Schibsted_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-grotesk", display: "swap" });
const newsreader = Newsreader({
  subsets: ["latin"], style: ["normal", "italic"], weight: ["400", "500"], variable: "--font-newsreader", display: "swap",
});
const geistMono = Geist_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: "Atrium",
  description: "One AI-native platform to acquire, serve, protect and administer every client relationship.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${grotesk.variable} ${newsreader.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body>
        <MotionProvider>
          <SessionProvider>
            <Shell>{children}</Shell>
          </SessionProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
