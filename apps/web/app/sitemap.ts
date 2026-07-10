/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
import type { MetadataRoute } from "next";

const baseUrl = "https://www.c2pro.io";

const languages = {
  es: `${baseUrl}/`,
  en: `${baseUrl}/en`,
  "x-default": `${baseUrl}/`,
};

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: `${baseUrl}/`,
      lastModified: new Date("2026-07-08T00:00:00.000Z"),
      priority: 1,
      alternates: {
        languages,
      },
    },
    {
      url: `${baseUrl}/en`,
      lastModified: new Date("2026-07-08T00:00:00.000Z"),
      priority: 0.9,
      alternates: {
        languages,
      },
    },
  ];
}
