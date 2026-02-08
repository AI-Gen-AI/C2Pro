'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';

export default function DashboardRedirect() {
  const { userRole, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;

    // Redirect based on user role
    if (userRole === 'c2pro_admin') {
      router.push('/admin/c2pro');
    } else if (userRole === 'tenant_admin') {
      router.push('/admin/tenant');
    } else {
      router.push('/dashboard/projects');
    }
  }, [userRole, isLoading, router]);

  return (
    <ProtectedRoute>
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="text-sm text-muted-foreground">Redirecting...</p>
        </div>
      </div>
    </ProtectedRoute>
  );
}
