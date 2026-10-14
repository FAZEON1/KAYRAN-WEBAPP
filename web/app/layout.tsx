import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const govde = Inter({ subsets: ["latin", "latin-ext"], variable: "--f-govde", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin", "latin-ext"], variable: "--f-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "KAYRAN", template: "%s · KAYRAN" },
  description: "KAYRAN yönetim uygulaması",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover" };

export default function KokDuzen({ children }: { children: React.ReactNode }) {
  return (
    <html lang="tr" className={`${govde.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
