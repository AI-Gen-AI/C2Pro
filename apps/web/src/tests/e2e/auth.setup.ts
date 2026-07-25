import { test as setup, expect } from "@playwright/test";
import { setupClerkTestingToken } from "@clerk/testing/playwright";

const authFile = "playwright/.auth/user.json";

setup("authenticate", async ({ page }) => {
  // 1. Setup Clerk testing token to bypass bot detection
  await setupClerkTestingToken({ page });

  // 2. Navigate to sign-in page
  await page.goto("/sign-in");

  // 3. Fill sign-in form (assuming custom identifiers if Clerk UI is customized, 
  // or standard Clerk ones if not)
  // For standard Clerk UI, we might need to wait for selectors
  await page.waitForSelector('[data-clerk-component="SignIn"]');
  
  // Fill email
  await page.locator('input[name="identifier"]').fill("testuser@c2pro.com");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  
  // Fill password
  await page.locator('input[name="password"]').fill("testpassword123!");
  await page.getByRole("button", { name: "Continue", exact: true }).click();

  // 4. Wait for successful login (redirect to projects)
  await page.waitForURL(/.*\/projects/);
  await expect(
    page.getByRole("heading", { name: "Projects", exact: true }),
  ).toBeVisible();

  // 5. Save storage state
  await page.context().storageState({ path: authFile });
});
