'use client';

import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import { Button } from '@/components/ui/button';

export function Navbar() {
  const { isAuthenticated, userRole } = useAuth();

  if (!isAuthenticated) {
    return null;
  }

  const dashboardLink = {
    user: '/dashboard/projects',
    tenant_admin: '/admin/tenant',
    c2pro_admin: '/admin/c2pro',
  }[userRole || 'user'];

  const dashboardLabel = {
    user: 'Dashboard',
    tenant_admin: 'Tenant Admin',
    c2pro_admin: 'System Admin',
  }[userRole || 'user'];

  return (
    <nav className="border-b bg-card sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link href={dashboardLink}>
          <div className="text-lg font-bold text-primary cursor-pointer hover:text-primary/80">
            C2Pro
          </div>
        </Link>
        <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary font-medium">
          {dashboardLabel}
        </span>
      </div>
    </nav>
  );
}
