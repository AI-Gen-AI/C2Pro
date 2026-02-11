import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import type { ReactNode } from "react";
import { Providers } from "@/app/providers";
import "./globals.css";

const inter = localFont({
  src: [
    {
      path: "../fonts/InterVariable-roman.woff2",
      style: "normal",
      weight: "100 900",
    },
    {
      path: "../fonts/InterVariable-italic.woff2",
      style: "italic",
      weight: "100 900",
    },
  ],
  variable: "--font-sans",
  display: "swap",
});

const jetbrains = localFont({
  src: [
    {
      path: "../fonts/JetBrainsMono-Regular.woff2",
      style: "normal",
      weight: "400",
    },
  ],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "C2Pro v3.0 - Coherence Monitor",
  description:
    "Enterprise Contract & Project Coherence Monitoring Platform. AI-powered cross-document analysis for construction and engineering projects.",
};

export const viewport: Viewport = {
  themeColor: "#00ACC1",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <body className="bg-background font-sans text-foreground antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
