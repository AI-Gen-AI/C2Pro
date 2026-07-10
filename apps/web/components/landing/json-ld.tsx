/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
import type { LandingLocale } from "./copy";

type LandingJsonLdProps = {
  locale: LandingLocale;
};

export function LandingJsonLd({ locale }: LandingJsonLdProps) {
  const description =
    locale === "en"
      ? "C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks with cited evidence and expert human validation."
      : "C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos con evidencia citada y validación humana experta.";

  const data = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": "https://www.c2pro.io/#organization",
        name: "C2Pro",
        url: "https://www.c2pro.io",
        email: "info@ai-gen.ai",
        parentOrganization: {
          "@type": "Organization",
          name: "AI-Gen",
          url: "https://www.ai-gen.ai",
          email: "info@ai-gen.ai",
        },
      },
      {
        "@type": "SoftwareApplication",
        "@id": "https://www.c2pro.io/#software",
        name: "C2Pro",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        description,
        url: locale === "en" ? "https://www.c2pro.io/en" : "https://www.c2pro.io/",
        provider: {
          "@id": "https://www.c2pro.io/#organization",
        },
        offers: {
          "@type": "Offer",
          availability: "https://schema.org/PreOrder",
          category: "Pilot program",
          url: locale === "en" ? "https://www.c2pro.io/en#waitlist" : "https://www.c2pro.io/#waitlist",
        },
      },
    ],
  };

  return (
    <script
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
      type="application/ld+json"
    />
  );
}
