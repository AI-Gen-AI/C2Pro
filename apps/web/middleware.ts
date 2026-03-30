/**
 * Clerk Middleware for Route Protection
 *
 * This middleware protects routes using Clerk v6 clerkMiddleware.
 * Public routes are accessible without authentication.
 * Protected routes redirect to /sign-in.
 *
 * @see https://clerk.com/docs/references/nextjs/clerk-middleware
 */

import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Public routes that don't require authentication
 */
const isPublicRoute = createRouteMatcher([
  // Landing & marketing pages
  "/",
  "/pricing",
  "/about",
  "/contact",

  // Auth pages (Clerk handles these)
  "/sign-in(.*)",
  "/sign-up(.*)",

  // Legacy auth redirects
  "/login",
  "/register",

  // API webhooks (Clerk webhooks)
  "/api/webhooks/clerk(.*)",

  // Health check
  "/api/health",

  // Demo mode entry
  "/demo(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  // Allow public routes without authentication
  if (isPublicRoute(req)) {
    return;
  }

  // Protect all other routes - redirects to sign-in if not authenticated
  await auth.protect();
});

export const config = {
  runtime: "nodejs",
  matcher: [
    // Skip Next.js internals and static files
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // Always run for API routes
    "/(api|trpc)(.*)",
  ],
};
