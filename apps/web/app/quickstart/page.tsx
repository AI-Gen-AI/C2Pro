'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Zap, BookOpen, Play, ArrowRight } from 'lucide-react';

export default function QuickStartPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/50 p-6">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-3 mb-8">
          <h1 className="text-4xl font-bold text-foreground">Welcome to C2Pro</h1>
          <p className="text-xl text-muted-foreground">
            Testing Different User Roles
          </p>
        </div>

        {/* Quick Info */}
        <Alert className="bg-blue-50 border-blue-200">
          <Zap className="h-4 w-4 text-blue-600" />
          <AlertDescription className="text-blue-800">
            <strong>Dev Mode Active:</strong> Look for the blue "Dev Mode" button in the bottom right corner to instantly switch between user roles.
          </AlertDescription>
        </Alert>

        {/* Three Main Actions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Action 1: Demo Roles */}
          <Link href="/demo-roles" className="group">
            <Card className="cursor-pointer hover:shadow-lg transition-all h-full group-hover:border-primary">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <Play className="h-5 w-5 text-primary" />
                  <CardTitle className="text-base">Demo Roles</CardTitle>
                </div>
                <CardDescription>See all roles at a glance</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Interactive role switcher with permissions table and detailed descriptions for each user type.
                </p>
                <p className="text-xs font-medium text-primary group-hover:underline">
                  Start testing →
                </p>
              </CardContent>
            </Card>
          </Link>

          {/* Action 2: Guide */}
          <Link href="/guide" className="group">
            <Card className="cursor-pointer hover:shadow-lg transition-all h-full group-hover:border-primary">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <BookOpen className="h-5 w-5 text-primary" />
                  <CardTitle className="text-base">Full Guide</CardTitle>
                </div>
                <CardDescription>Learn how everything works</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  Complete walkthrough of all roles, URLs, and testing workflows with detailed explanations.
                </p>
                <p className="text-xs font-medium text-primary group-hover:underline">
                  Read guide →
                </p>
              </CardContent>
            </Card>
          </Link>

          {/* Action 3: Landing */}
          <Link href="/" className="group">
            <Card className="cursor-pointer hover:shadow-lg transition-all h-full group-hover:border-primary">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <ArrowRight className="h-5 w-5 text-primary" />
                  <CardTitle className="text-base">Landing Page</CardTitle>
                </div>
                <CardDescription>See the public interface</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  View the public landing page with platform overview, features, and statistics.
                </p>
                <p className="text-xs font-medium text-primary group-hover:underline">
                  View landing →
                </p>
              </CardContent>
            </Card>
          </Link>
        </div>

        {/* The Three Roles */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold text-foreground">The Three User Roles</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Regular User */}
            <Card className="border-blue-200 bg-blue-50/50">
              <CardHeader>
                <CardTitle className="text-lg">👤 Regular User</CardTitle>
                <CardDescription>Personal project management</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>View and manage their own projects</p>
                <div className="pt-2 border-t">
                  <p className="font-medium mb-1">Try at:</p>
                  <code className="text-xs bg-white px-2 py-1 rounded block">
                    /dashboard/projects
                  </code>
                </div>
              </CardContent>
            </Card>

            {/* Tenant Admin */}
            <Card className="border-purple-200 bg-purple-50/50">
              <CardHeader>
                <CardTitle className="text-lg">🛡️ Tenant Admin</CardTitle>
                <CardDescription>Organization management</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>Manage all projects and users in the organization</p>
                <div className="pt-2 border-t">
                  <p className="font-medium mb-1">Try at:</p>
                  <code className="text-xs bg-white px-2 py-1 rounded block">
                    /admin/tenant
                  </code>
                </div>
              </CardContent>
            </Card>

            {/* C2Pro Admin */}
            <Card className="border-amber-200 bg-amber-50/50">
              <CardHeader>
                <CardTitle className="text-lg">👑 C2Pro Admin</CardTitle>
                <CardDescription>Platform administration</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>Manage all tenants and system configuration</p>
                <div className="pt-2 border-t">
                  <p className="font-medium mb-1">Try at:</p>
                  <code className="text-xs bg-white px-2 py-1 rounded block">
                    /admin/c2pro
                  </code>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* How to Test */}
        <Card>
          <CardHeader>
            <CardTitle>How to Test Each Role</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <p className="font-medium text-foreground">Step 1: Find the Dev Mode Button</p>
              <p className="text-sm text-muted-foreground">
                Look for the blue "Dev Mode" button in the <strong>bottom right corner</strong> of your screen.
              </p>
            </div>

            <div className="space-y-2">
              <p className="font-medium text-foreground">Step 2: Click to Open Role Menu</p>
              <p className="text-sm text-muted-foreground">
                Click the button to see a dropdown menu with three role options.
              </p>
            </div>

            <div className="space-y-2">
              <p className="font-medium text-foreground">Step 3: Select a Role</p>
              <p className="text-sm text-muted-foreground">
                Choose "User", "Tenant Admin", or "C2Pro Admin" to switch roles instantly.
              </p>
            </div>

            <div className="space-y-2">
              <p className="font-medium text-foreground">Step 4: Navigate to Dashboard</p>
              <p className="text-sm text-muted-foreground">
                Visit one of the role-specific URLs listed above to see the interface for that role.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Quick Links Table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">All Available URLs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm">
              <div>
                <p className="font-medium text-foreground mb-2">Public (No Login)</p>
                <div className="space-y-1 ml-3 text-muted-foreground">
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/</code> - Landing page</p>
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/login</code> - Login</p>
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/signup</code> - Sign up</p>
                </div>
              </div>

              <div className="border-t pt-3">
                <p className="font-medium text-foreground mb-2">User Dashboards</p>
                <div className="space-y-1 ml-3 text-muted-foreground">
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/dashboard/projects</code> - User projects</p>
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/dashboard/projects/demo</code> - Demo analysis</p>
                </div>
              </div>

              <div className="border-t pt-3">
                <p className="font-medium text-foreground mb-2">Tenant Admin</p>
                <div className="space-y-1 ml-3 text-muted-foreground">
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/admin/tenant</code> - Overview</p>
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/admin/tenant/users</code> - User management</p>
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/admin/tenant/settings</code> - Settings</p>
                </div>
              </div>

              <div className="border-t pt-3">
                <p className="font-medium text-foreground mb-2">C2Pro Admin</p>
                <div className="space-y-1 ml-3 text-muted-foreground">
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/admin/c2pro</code> - Overview</p>
                  <p><code className="bg-muted px-1.5 py-0.5 rounded">/admin/c2pro/settings</code> - Settings</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* CTA */}
        <div className="flex gap-3 justify-center pt-4">
          <Link href="/demo-roles">
            <Button size="lg" className="gap-2">
              Try Demo Roles
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/guide">
            <Button size="lg" variant="outline" className="gap-2">
              <BookOpen className="h-4 w-4" />
              Full Guide
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
