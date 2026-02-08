'use client';

import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowRight, Shield, Users, Briefcase } from 'lucide-react';
import Link from 'next/link';

export default function DashboardHome() {
  const { isAuthenticated, userRole, logout } = useAuth();
  const router = useRouter();

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold">Access Denied</h1>
          <p className="text-muted-foreground">Please log in to continue</p>
          <Link href="/login">
            <Button>Go to Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  const roleInfo = {
    user: {
      title: 'User Dashboard',
      description: 'View and manage your projects',
      icon: Briefcase,
      link: '/dashboard/projects',
      color: 'blue',
    },
    tenant_admin: {
      title: 'Tenant Admin Dashboard',
      description: 'Manage all projects in your organization',
      icon: Shield,
      link: '/admin/tenant',
      color: 'purple',
    },
    c2pro_admin: {
      title: 'C2Pro Admin Panel',
      description: 'Manage all tenants and system settings',
      icon: Users,
      link: '/admin/c2pro',
      color: 'amber',
    },
  };

  const currentRole = roleInfo[userRole as keyof typeof roleInfo] || roleInfo.user;
  const CurrentIcon = currentRole.icon;

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/50 p-6">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-4xl font-bold">Welcome back</h1>
          <p className="text-lg text-muted-foreground">
            You are logged in as: <span className="font-semibold capitalize">{userRole.replace('_', ' ')}</span>
          </p>
        </div>

        {/* Current Role Card */}
        <Card className="border-2">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <CurrentIcon className="h-5 w-5" />
              {currentRole.title}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">{currentRole.description}</p>
            <Link href={currentRole.link}>
              <Button className="gap-2">
                Open Dashboard
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Quick Links */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Quick Links</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link href="/guide">
              <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                <CardHeader>
                  <CardTitle className="text-base">View Guide</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  Learn about all available features and dashboards
                </CardContent>
              </Card>
            </Link>
            <Link href="/demo-roles">
              <Card className="hover:shadow-md transition-shadow cursor-pointer h-full">
                <CardHeader>
                  <CardTitle className="text-base">Switch Roles (Dev)</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground">
                  Try different user roles to see different dashboards
                </CardContent>
              </Card>
            </Link>
          </div>
        </div>

        {/* Logout */}
        <div className="flex justify-end pt-4">
          <Button variant="outline" onClick={logout}>
            Logout
          </Button>
        </div>
      </div>
    </div>
  );
}
