/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
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
  metadataBase: new URL("https://www.c2pro.io"),
  title: {
    default: "C2Pro · Inteligencia documental para compras y contratos",
    template: "%s · C2Pro",
  },
  description:
    "C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos, con evidencia citada y validación humana experta. Únete al piloto.",
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  themeColor: "#0B1F3A",
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
