/**
 * Clerk Proxy for Route Protection
 *
 * Next.js 16 renamed middleware to proxy and runs it on the Node.js runtime.
 * Public routes are accessible without authentication.
 * Protected routes redirect to /sign-in.
 *
 * @see https://clerk.com/docs/reference/nextjs/clerk-middleware
 * @see https://nextjs.org/docs/app/api-reference/file-conventions/proxy
 */

import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Public routes that don't require authentication
 */
const isPublicRoute = createRouteMatcher([
  "/",
  "/pricing",
  "/about",
  "/contact",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/login",
  "/register",
  "/api/webhooks/clerk(.*)",
  "/api/health",
  "/demo(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  if (isPublicRoute(req)) {
    return;
  }

  await auth.protect();
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
