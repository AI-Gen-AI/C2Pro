'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import LandingPageContent from '@/components/landing-page-content';

export default function RootPage() {
  const { isAuthenticated, isLoading, userRole } = useAuth();
  const router = useRouter();
  const [showLanding, setShowLanding] = useState(false);
  const [lastRole, setLastRole] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading) return;

    // If authenticated, redirect based on role (including demo role changes)
    if (isAuthenticated) {
      // If role changed, navigate to appropriate dashboard
      if (userRole !== lastRole) {
        setLastRole(userRole);
        
        if (userRole === 'c2pro_admin') {
          router.push('/admin/c2pro');
        } else if (userRole === 'tenant_admin') {
          router.push('/admin/tenant');
        } else {
          router.push('/dashboard/projects');
        }
      }
    } else {
      // Not authenticated, show landing page
      setShowLanding(true);
    }
  }, [isAuthenticated, isLoading, userRole, router, lastRole]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center space-y-4">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (showLanding) {
    return <LandingPageContent />;
  }

  return null;
}
