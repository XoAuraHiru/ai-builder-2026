import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";

export const metadata: Metadata = { title: "Atrium", description: "AI-native wealth operating system" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 py-6 text-xs text-slate-500">
          Prototype with synthetic data and paper trading. Nothing here is investment advice.
        </footer>
      </body>
    </html>
  );
}
