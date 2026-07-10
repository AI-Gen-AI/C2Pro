/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: {
    absolute: "C2Pro · Inteligencia documental para compras y contratos",
  },
  description:
    "C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos, con evidencia citada y validación humana experta. Únete al piloto.",
  alternates: {
    canonical: "/",
    languages: {
      es: "/",
      en: "/en",
      "x-default": "/",
    },
  },
  openGraph: {
    type: "website",
    locale: "es_ES",
    siteName: "C2Pro",
    url: "/",
    title: "C2Pro · Inteligencia documental para compras y contratos",
    description:
      "C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos, con evidencia citada y validación humana experta. Únete al piloto.",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootPage() {
  return <LandingPage locale="es" />;
}
