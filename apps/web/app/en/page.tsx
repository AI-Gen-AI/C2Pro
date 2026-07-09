/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200, TASK-FRT-202
 */
import type { Metadata } from "next";
import { LandingPage } from "@/components/landing/landing-page";

export const metadata: Metadata = {
  title: {
    absolute: "C2Pro · Document intelligence for procurement and contracts",
  },
  description:
    "C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks — with cited evidence and expert human validation. Join the pilot.",
  alternates: {
    canonical: "/en",
    languages: {
      es: "/",
      en: "/en",
      "x-default": "/",
    },
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "C2Pro",
    url: "/en",
    title: "C2Pro · Document intelligence for procurement and contracts",
    description:
      "C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks — with cited evidence and expert human validation. Join the pilot.",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export default function EnglishLandingPage() {
  return <LandingPage locale="en" />;
}
