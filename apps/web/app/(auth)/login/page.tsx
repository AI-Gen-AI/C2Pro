/**
 * Login Page - DEPRECATED
 *
 * This page now redirects to /sign-in which uses Clerk authentication.
 * Kept for backwards compatibility with existing links/bookmarks.
 */

import { redirect } from "next/navigation";

export default function LoginPage() {
  redirect("/sign-in");
}
