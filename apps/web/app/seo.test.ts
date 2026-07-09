/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/font/local", () => ({
  default: () => ({
    className: "font",
    style: { fontFamily: "Font" },
    variable: "font-variable",
  }),
}));

vi.mock("@/app/providers", () => ({
  Providers: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/components/landing/landing-page", () => ({
  LandingPage: ({ locale }: { locale: string }) => `Landing ${locale}`,
}));

describe("landing SEO metadata", () => {
  it("sets brand defaults at the root layout", async () => {
    const { metadata, viewport } = await import("./layout");

    expect(metadata.metadataBase?.toString()).toBe("https://www.c2pro.io/");
    expect(metadata.title).toEqual({
      default: "C2Pro · Inteligencia documental para compras y contratos",
      template: "%s · C2Pro",
    });
    expect(metadata.description).toBe(
      "C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos, con evidencia citada y validación humana experta. Únete al piloto.",
    );
    expect(viewport.themeColor).toBe("#0B1F3A");
  });

  it("exports reciprocal Spanish metadata for /", async () => {
    const { metadata } = await import("./page");

    // `absolute` opts out of the layout's `%s · C2Pro` template, which would
    // double the brand on titles that already start with "C2Pro ·".
    expect(metadata.title).toEqual({
      absolute: "C2Pro · Inteligencia documental para compras y contratos",
    });
    expect(metadata.alternates).toEqual({
      canonical: "/",
      languages: {
        es: "/",
        en: "/en",
        "x-default": "/",
      },
    });
    expect(metadata.openGraph).toMatchObject({
      type: "website",
      locale: "es_ES",
      siteName: "C2Pro",
      url: "/",
    });
    expect(metadata.twitter).toEqual({ card: "summary_large_image" });
  });

  it("exports reciprocal English metadata for /en", async () => {
    const { metadata } = await import("./en/page");

    expect(metadata.title).toEqual({
      absolute: "C2Pro · Document intelligence for procurement and contracts",
    });
    expect(metadata.description).toBe(
      "C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks — with cited evidence and expert human validation. Join the pilot.",
    );
    expect(metadata.alternates).toEqual({
      canonical: "/en",
      languages: {
        es: "/",
        en: "/en",
        "x-default": "/",
      },
    });
    expect(metadata.openGraph).toMatchObject({
      type: "website",
      locale: "en_US",
      siteName: "C2Pro",
      url: "/en",
    });
  });
});

describe("landing structured data", () => {
  it("renders Organization and SoftwareApplication JSON-LD without invented ratings", async () => {
    const { LandingJsonLd } = await import("@/components/landing/json-ld");

    const markup = renderToStaticMarkup(LandingJsonLd({ locale: "es" }));
    const jsonText = markup.match(/<script[^>]*>(.*)<\/script>/)?.[1];
    const data = JSON.parse(jsonText ?? "{}");

    expect(data["@graph"]).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          "@type": "Organization",
          name: "C2Pro",
          parentOrganization: expect.objectContaining({
            "@type": "Organization",
            name: "AI-Gen",
            url: "https://www.ai-gen.ai",
          }),
        }),
        expect.objectContaining({
          "@type": "SoftwareApplication",
          name: "C2Pro",
          applicationCategory: "BusinessApplication",
          operatingSystem: "Web",
        }),
      ]),
    );
    expect(markup).not.toContain("aggregateRating");
    expect(markup).not.toContain("ratingValue");
  });
});

describe("landing sitemap and robots", () => {
  it("returns canonical ES and EN sitemap entries with reciprocal alternates", async () => {
    const { default: sitemap } = await import("./sitemap");

    expect(sitemap()).toEqual([
      expect.objectContaining({
        url: "https://www.c2pro.io/",
        priority: 1,
        alternates: {
          languages: {
            es: "https://www.c2pro.io/",
            en: "https://www.c2pro.io/en",
            "x-default": "https://www.c2pro.io/",
          },
        },
      }),
      expect.objectContaining({
        url: "https://www.c2pro.io/en",
        alternates: {
          languages: {
            es: "https://www.c2pro.io/",
            en: "https://www.c2pro.io/en",
            "x-default": "https://www.c2pro.io/",
          },
        },
      }),
    ]);
  });

  it("allows public landing/demo routes and disallows private/API routes", async () => {
    const { default: robots } = await import("./robots");

    expect(robots()).toEqual({
      rules: {
        userAgent: "*",
        allow: ["/", "/en", "/demo"],
        disallow: ["/dashboard", "/projects", "/admin", "/api", "/(app)"],
      },
      sitemap: "https://www.c2pro.io/sitemap.xml",
    });
  });
});

describe("landing Open Graph image metadata", () => {
  it("exports the expected OG image contract", async () => {
    const image = await import("./opengraph-image");

    expect(image.alt).toBe("C2Pro · Inteligencia documental para compras y contratos");
    expect(image.size).toEqual({ width: 1200, height: 630 });
    expect(image.contentType).toBe("image/png");
  });
});
