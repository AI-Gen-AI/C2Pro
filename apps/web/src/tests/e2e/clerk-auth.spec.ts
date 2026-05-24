import { test, expect } from "@playwright/test";
import { setupClerkTestingToken } from "@clerk/testing/playwright";

/**
 * TS-SEC-CLK-001: Clerk Authentication Efficiency Test
 * 
 * Demonstrates the usage of clerk-testing skill:
 * 1. setupClerkTestingToken() for bypassing bot detection
 * 2. Relying on global setup/storageState for speed
 */

test.describe("Clerk Authentication Efficiency", () => {
  // We don't need a beforeEach that logs in because we use storageState in playwright.config.ts
  
  test("should access protected dashboard directly using saved auth state", async ({ page }) => {
    // Navigate directly to a protected route
    await page.goto("/projects");
    
    // We should be redirected to /projects and see the dashboard
    // if storageState worked correctly.
    await expect(page).toHaveURL(/.*\/projects/);
    await expect(page.locator('h1:has-text("Projects")')).toBeVisible();
  });

  test("should handle re-authentication with testing token if needed", async ({ page }) => {
    /**
     * If we ever need to go back to sign-in or sign-up pages during a test,
     * we must call setupClerkTestingToken.
     */
    await setupClerkTestingToken({ page });
    
    await page.goto("/sign-in");
    
    // Bypasses bot detection, allowing us to interact with Clerk UI programmatically
    await expect(page.locator('[data-clerk-component="SignIn"]')).toBeVisible();
  });
});
