/**
 * Register Page - DEPRECATED
 *
 * This page now redirects to /sign-up which uses Clerk authentication.
 * Kept for backwards compatibility with existing links/bookmarks.
 */

import { redirect } from "next/navigation";

export default function RegisterPage() {
  redirect("/sign-up");
}
