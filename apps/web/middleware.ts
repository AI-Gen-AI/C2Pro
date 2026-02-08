/**
 * Middleware for role-based routing
 * Redirects users based on their role and requested path
 */

import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Get auth token from cookies
  const token = request.cookies.get('c2pro_access_token')?.value;
  const userRole = request.cookies.get('c2pro_user_role')?.value;

  // Public routes that don't require authentication
  const publicRoutes = ['/', '/login', '/signup'];
  const isPublicRoute = publicRoutes.includes(pathname);

  // If user is not authenticated and tries to access protected route
  if (!token && !isPublicRoute && !pathname.startsWith('/auth')) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // If user is authenticated, redirect based on role
  if (token && (pathname === '/login' || pathname === '/signup')) {
    // Redirect to appropriate dashboard based on role
    if (userRole === 'c2pro_admin') {
      return NextResponse.redirect(new URL('/admin/c2pro', request.url));
    } else if (userRole === 'tenant_admin') {
      return NextResponse.redirect(new URL('/admin/tenant', request.url));
    } else {
      return NextResponse.redirect(new URL('/dashboard', request.url));
    }
  }

  // Protect admin routes
  if (pathname.startsWith('/admin/c2pro') && userRole !== 'c2pro_admin' && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  if (pathname.startsWith('/admin/tenant') && userRole !== 'tenant_admin' && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico).*)',
  ],
};
