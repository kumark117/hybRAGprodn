import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";
import Link from "next/link";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Production-grade Hybrid RAG Console",
  description: "Production-oriented hybrid RAG with live pipeline observability",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable}`} style={{ fontFamily: "var(--font-sans), sans-serif" }}>
        <div className="shell">
          <header className="topbar">
            <div className="brand">
              <strong>Production-grade Hybrid RAG</strong>
              <span>retrieval · fusion · live observability</span>
            </div>
            <nav className="nav">
              <Link href="/">Home</Link>
              <Link href="/query">Query</Link>
              <Link href="/indexing">Index</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
