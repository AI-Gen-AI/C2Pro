'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ArrowRight, Zap, Lock } from 'lucide-react';

export default function GuidePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/50 p-6">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2 mb-8">
          <h1 className="text-4xl font-bold text-foreground">C2Pro Interface Guide</h1>
          <p className="text-lg text-muted-foreground">
            Learn how to navigate between different user roles and interfaces
          </p>
        </div>

        {/* Dev Mode Info */}
        <Alert className="bg-blue-50 border-blue-200">
          <Zap className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            <strong>Development Mode:</strong> Click the floating blue "Dev Mode" button in the bottom right corner to switch between roles instantly.
          </AlertDescription>
        </Alert>

        {/* Quick Links */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link href="/demo-roles">
            <Card className="cursor-pointer hover:shadow-lg transition-shadow">
              <CardHeader>
                <CardTitle className="text-base">Role Demo</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Switch between roles and see what each user can access.
                </p>
              </CardContent>
            </Card>
          </Link>

          <Link href="/">
            <Card className="cursor-pointer hover:shadow-lg transition-shadow">
              <CardHeader>
                <CardTitle className="text-base">Landing Page</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Public landing page with platform overview.
                </p>
              </CardContent>
            </Card>
          </Link>

          <Link href="/login">
            <Card className="cursor-pointer hover:shadow-lg transition-shadow">
              <CardHeader>
                <CardTitle className="text-base">Login</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Sign in with your credentials or demo account.
                </p>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* User Roles Section */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">User Roles</h2>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <span className="text-blue-500">👤</span> Regular User
              </CardTitle>
              <CardDescription>Personal project management</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="font-medium text-sm mb-2">Capabilities:</p>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>View and manage your own projects</li>
                  <li>Upload documents for analysis</li>
                  <li>View analysis results and reports</li>
                  <li>Access your account settings</li>
                </ul>
              </div>
              <div>
                <p className="font-medium text-sm mb-2">Main URLs:</p>
                <div className="space-y-1 text-sm">
                  <code className="bg-muted px-2 py-1 rounded block">/dashboard/projects</code>
                  <code className="bg-muted px-2 py-1 rounded block">/dashboard/projects/demo</code>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <span className="text-purple-500">🛡️</span> Tenant Admin
              </CardTitle>
              <CardDescription>Tenant-wide management and oversight</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="font-medium text-sm mb-2">Capabilities:</p>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>View ALL projects in the tenant</li>
                  <li>Manage tenant users and permissions</li>
                  <li>Configure tenant settings</li>
                  <li>View tenant analytics and reports</li>
                  <li>Manage billing and subscriptions</li>
                </ul>
              </div>
              <div>
                <p className="font-medium text-sm mb-2">Main URLs:</p>
                <div className="space-y-1 text-sm">
                  <code className="bg-muted px-2 py-1 rounded block">/admin/tenant</code>
                  <code className="bg-muted px-2 py-1 rounded block">/admin/tenant/users</code>
                  <code className="bg-muted px-2 py-1 rounded block">/admin/tenant/settings</code>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <span className="text-amber-500">👑</span> C2Pro Admin
              </CardTitle>
              <CardDescription>Platform-wide administration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="font-medium text-sm mb-2">Capabilities:</p>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>Manage all tenants in the platform</li>
                  <li>Create new tenants and users</li>
                  <li>Configure system settings</li>
                  <li>Monitor platform health and usage</li>
                  <li>Manage security and integrations</li>
                </ul>
              </div>
              <div>
                <p className="font-medium text-sm mb-2">Main URLs:</p>
                <div className="space-y-1 text-sm">
                  <code className="bg-muted px-2 py-1 rounded block">/admin/c2pro</code>
                  <code className="bg-muted px-2 py-1 rounded block">/admin/c2pro/settings</code>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* How to Test */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">How to Test Different Roles</h2>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Method 1: Use Dev Mode Button</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <ol className="space-y-2 list-decimal list-inside text-muted-foreground">
                <li>Look for the blue "Dev Mode" button in the bottom right corner</li>
                <li>Click to open the role selector menu</li>
                <li>Choose a role (User, Tenant Admin, or C2Pro Admin)</li>
                <li>Navigate to any page to see how it appears for that role</li>
              </ol>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Method 2: Use Role Demo Page</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <ol className="space-y-2 list-decimal list-inside text-muted-foreground">
                <li>Go to <code className="bg-muted px-1.5 py-0.5 rounded">/demo-roles</code></li>
                <li>Click on any role card to select it</li>
                <li>View a detailed breakdown of that role's permissions</li>
                <li>Click "View Dashboard" to navigate to that role's interface</li>
              </ol>
            </CardContent>
          </Card>
        </div>

        {/* Navigation Map */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">Navigation Map</h2>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Route Structure</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm font-mono">
                <div className="space-y-1">
                  <p className="font-semibold text-foreground">Public Routes</p>
                  <p className="text-muted-foreground ml-2">/ - Landing page</p>
                  <p className="text-muted-foreground ml-2">/login - Login page</p>
                  <p className="text-muted-foreground ml-2">/signup - Registration page</p>
                </div>

                <div className="space-y-1 border-t pt-3">
                  <p className="font-semibold text-foreground">User Routes (requires authentication)</p>
                  <p className="text-muted-foreground ml-2">/dashboard/projects - Project list</p>
                  <p className="text-muted-foreground ml-2">/dashboard/projects/demo - Demo analysis</p>
                </div>

                <div className="space-y-1 border-t pt-3">
                  <p className="font-semibold text-foreground">Tenant Admin Routes</p>
                  <p className="text-muted-foreground ml-2">/admin/tenant - Projects overview</p>
                  <p className="text-muted-foreground ml-2">/admin/tenant/users - User management</p>
                  <p className="text-muted-foreground ml-2">/admin/tenant/settings - Settings</p>
                </div>

                <div className="space-y-1 border-t pt-3">
                  <p className="font-semibold text-foreground">C2Pro Admin Routes</p>
                  <p className="text-muted-foreground ml-2">/admin/c2pro - Tenant overview</p>
                  <p className="text-muted-foreground ml-2">/admin/c2pro/settings - System settings</p>
                </div>

                <div className="space-y-1 border-t pt-3">
                  <p className="font-semibold text-foreground">Demo/Testing Routes</p>
                  <p className="text-muted-foreground ml-2">/demo-roles - Role switcher & permissions table</p>
                  <p className="text-muted-foreground ml-2">/guide - This page</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* CTA */}
        <div className="text-center pt-4">
          <Link href="/demo-roles">
            <Button size="lg" className="gap-2">
              Try Role Demo Now
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
