'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, User, Shield, Crown } from 'lucide-react';
import Link from 'next/link';

type UserRole = 'user' | 'tenant_admin' | 'c2pro_admin';

interface DemoView {
  role: UserRole;
  label: string;
  description: string;
  icon: React.ReactNode;
  path: string;
  color: string;
}

const DEMO_VIEWS: DemoView[] = [
  {
    role: 'user',
    label: 'Regular User',
    description: 'View and manage your own projects. Upload documents for analysis.',
    icon: <User className="h-5 w-5" />,
    path: '/dashboard/projects',
    color: 'bg-blue-50 border-blue-200',
  },
  {
    role: 'tenant_admin',
    label: 'Tenant Admin',
    description: 'View all projects in your tenant. Manage users and settings.',
    icon: <Shield className="h-5 w-5" />,
    path: '/admin/tenant',
    color: 'bg-purple-50 border-purple-200',
  },
  {
    role: 'c2pro_admin',
    label: 'C2Pro Admin',
    description: 'Manage all tenants and system settings. Full platform control.',
    icon: <Crown className="h-5 w-5" />,
    path: '/admin/c2pro',
    color: 'bg-amber-50 border-amber-200',
  },
];

export default function DemoModePage() {
  const { setDemoRole, userRole } = useAuth();
  const [selectedRole, setSelectedRole] = useState<UserRole>('user');

  const handleRoleChange = (role: UserRole) => {
    setSelectedRole(role);
    setDemoRole?.(role);
  };

  const currentView = DEMO_VIEWS.find((v) => v.role === selectedRole);

  if (!setDemoRole) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-4xl mx-auto">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Demo mode is only available in development environment. This page cannot be used in production.
            </AlertDescription>
          </Alert>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/50 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">Role Demo Mode</h1>
          <p className="text-muted-foreground">
            Switch between different user roles to preview how each interface appears
          </p>
        </div>

        {/* Alert */}
        <Alert className="mb-8 bg-amber-50 border-amber-200">
          <AlertCircle className="h-4 w-4 text-amber-600" />
          <AlertDescription className="text-amber-800">
            <strong>Development Mode:</strong> This demo allows you to switch roles without authentication.
            This feature is disabled in production.
          </AlertDescription>
        </Alert>

        {/* Role Selector Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {DEMO_VIEWS.map((view) => (
            <Card
              key={view.role}
              className={`cursor-pointer transition-all ${
                selectedRole === view.role
                  ? 'ring-2 ring-primary shadow-lg'
                  : 'hover:shadow-md'
              } ${view.color}`}
              onClick={() => handleRoleChange(view.role)}
            >
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="text-primary">{view.icon}</div>
                  <CardTitle className="text-lg">{view.label}</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{view.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Current View Info */}
        {currentView && (
          <div className="space-y-6">
            {/* Info Card */}
            <Card className="bg-card border">
              <CardHeader>
                <CardTitle>Preview: {currentView.label}</CardTitle>
                <CardDescription>
                  You are now viewing the interface as a {currentView.label.toLowerCase()}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-foreground">Current Role:</p>
                  <div className="inline-flex items-center gap-2 px-3 py-1 bg-muted rounded-full text-sm">
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                    {currentView.label}
                  </div>
                </div>

                <div className="space-y-2">
                  <p className="text-sm font-medium text-foreground">What you can do:</p>
                  <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                    {currentView.role === 'user' && (
                      <>
                        <li>View your own projects</li>
                        <li>Upload and analyze documents</li>
                        <li>View analysis results</li>
                        <li>Access project settings</li>
                      </>
                    )}
                    {currentView.role === 'tenant_admin' && (
                      <>
                        <li>View all tenant projects</li>
                        <li>Manage tenant users</li>
                        <li>Configure tenant settings</li>
                        <li>View tenant analytics</li>
                      </>
                    )}
                    {currentView.role === 'c2pro_admin' && (
                      <>
                        <li>Manage all tenants</li>
                        <li>Create new tenants and users</li>
                        <li>System configuration</li>
                        <li>Monitor platform health</li>
                      </>
                    )}
                  </ul>
                </div>
              </CardContent>
            </Card>

            {/* Navigation Card */}
            <Card className="bg-card border">
              <CardHeader>
                <CardTitle className="text-base">Navigate to Interface</CardTitle>
              </CardHeader>
              <CardContent>
                <Link href={currentView.path}>
                  <Button className="w-full" size="lg">
                    View {currentView.label} Dashboard
                    <span className="ml-2">→</span>
                  </Button>
                </Link>
              </CardContent>
            </Card>

            {/* Features Table */}
            <Card className="bg-card border">
              <CardHeader>
                <CardTitle className="text-base">Role Permissions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-3 font-medium">Feature</th>
                        <th className="text-center py-3 px-3 font-medium">User</th>
                        <th className="text-center py-3 px-3 font-medium">Tenant Admin</th>
                        <th className="text-center py-3 px-3 font-medium">C2Pro Admin</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { feature: 'View own projects', user: true, tenant: true, c2pro: true },
                        { feature: 'View all tenant projects', user: false, tenant: true, c2pro: true },
                        { feature: 'Manage project access', user: false, tenant: true, c2pro: true },
                        { feature: 'Create users', user: false, tenant: true, c2pro: true },
                        { feature: 'Manage tenants', user: false, tenant: false, c2pro: true },
                        { feature: 'System settings', user: false, tenant: false, c2pro: true },
                        { feature: 'Billing management', user: false, tenant: true, c2pro: true },
                      ].map((row) => (
                        <tr key={row.feature} className="border-b hover:bg-muted/50">
                          <td className="py-3 px-3 text-foreground">{row.feature}</td>
                          <td className="text-center py-3 px-3">
                            {row.user ? (
                              <span className="text-green-600 font-medium">✓</span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </td>
                          <td className="text-center py-3 px-3">
                            {row.tenant ? (
                              <span className="text-green-600 font-medium">✓</span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </td>
                          <td className="text-center py-3 px-3">
                            {row.c2pro ? (
                              <span className="text-green-600 font-medium">✓</span>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
