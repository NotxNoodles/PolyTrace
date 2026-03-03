import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolyTrace — Polymarket Insider & Oracle Tracker",
  description:
    "Track Smart Money wallets and correlate prediction market probabilities against live spot markets.",
};

const NAV_ITEMS = [
  { href: "/", label: "Dashboard" },
  { href: "/smart-money", label: "Smart Money" },
  { href: "/oracle", label: "Oracle Scanner" },
] as const;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen flex flex-col">
        <header className="sticky top-0 z-50 border-b border-surface-300 bg-surface/80 backdrop-blur-xl">
          <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
            <Link href="/" className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-accent-green to-accent-blue" />
              <span className="text-lg font-bold tracking-tight">
                Poly<span className="text-accent-green">Trace</span>
              </span>
            </Link>

            <nav className="flex items-center gap-1">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-lg px-3 py-1.5 text-sm text-gray-400 transition-colors hover:bg-surface-200 hover:text-gray-100"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
          {children}
        </main>

        <footer className="border-t border-surface-300 py-4 text-center text-xs text-gray-600">
          PolyTrace v0.1.0 — Not financial advice
        </footer>
      </body>
    </html>
  );
}
