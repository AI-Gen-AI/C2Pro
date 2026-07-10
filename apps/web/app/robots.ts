/**
 * Test Suite ID: TASK-FRT-202
 * Backlog Task: TASK-FRT-202
 */
import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/en", "/demo"],
      disallow: ["/dashboard", "/projects", "/admin", "/api", "/(app)"],
    },
    sitemap: "https://www.c2pro.io/sitemap.xml",
  };
}
