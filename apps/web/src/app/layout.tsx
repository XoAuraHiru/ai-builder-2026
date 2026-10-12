import type { Metadata } from "next";
import { Archivo, Source_Serif_4 } from "next/font/google";
import "./globals.css";
import { MotionProvider } from "@/components/motion-provider";
import { Shell } from "@/components/shell";
import { SessionProvider } from "@/lib/session-context";

const archivo = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--font-archivo", display: "swap" });
const sourceSerif = Source_Serif_4({
  subsets: ["latin"], style: ["normal", "italic"], variable: "--font-source-serif", display: "swap",
});

export const metadata: Metadata = {
  title: "Atrium",
  description: "One AI-native platform to acquire, serve, protect and administer every client relationship.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${archivo.variable} ${sourceSerif.variable}`} suppressHydrationWarning>
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
