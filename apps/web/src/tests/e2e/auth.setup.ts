import { expect, test as setup } from "@playwright/test";
import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";

const authFile = "playwright/.auth/user.json";
const clerkE2eUserId = "user_3H0l5NCcPYLnfWokjdm2D8m3iGR";

setup("authenticate", async ({ page }) => {
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await clerk.signIn({
    page,
    signInParams: {
      strategy: "password",
      identifier: "testuser@c2pro.com",
      password: "Testpasword123",
    },
  });

  const sessionSubject = await page.evaluate(async () => {
    const token = await window.Clerk?.session?.getToken();
    if (!token) return null;

    const payload = token.split(".")[1];
    if (!payload) return null;

    const normalizedPayload = payload.replace(/-/g, "+").replace(/_/g, "/");
    return (JSON.parse(atob(normalizedPayload)) as { sub?: unknown }).sub;
  });
  expect(sessionSubject).toBe(clerkE2eUserId);

  await page.goto("/projects");
  await expect(page.locator('h1:has-text("Projects")')).toBeVisible();
  await page.context().storageState({ path: authFile });
});
