'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ArrowRight, Users, Building2, Shield } from 'lucide-react';

export default function FlowDemoPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/50 p-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-4">C2Pro Authentication Flow</h1>
          <p className="text-lg text-muted-foreground">
            Complete role-based architecture with three user types
          </p>
        </div>

        {/* Flow Diagram */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
          {/* Regular User */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-blue-600" />
                <CardTitle>Regular User</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Project team members who upload and analyze documents
              </p>
              <div className="space-y-2">
                <div className="text-sm">
                  <p className="font-medium">Permissions:</p>
                  <ul className="text-xs text-muted-foreground mt-1 space-y-1">
                    <li>✓ View own projects</li>
                    <li>✓ Create projects</li>
                    <li>✓ Upload documents</li>
                    <li>✓ Run analysis</li>
                  </ul>
                </div>
              </div>
              <Link href="/signup">
                <Button className="w-full" size="sm">
                  Sign Up as User
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Tenant Admin */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-purple-600" />
                <CardTitle>Tenant Admin</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Company administrators managing all tenant projects and users
              </p>
              <div className="space-y-2">
                <div className="text-sm">
                  <p className="font-medium">Permissions:</p>
                  <ul className="text-xs text-muted-foreground mt-1 space-y-1">
                    <li>✓ View all projects</li>
                    <li>✓ Manage users</li>
                    <li>✓ View analytics</li>
                    <li>✓ Tenant settings</li>
                  </ul>
                </div>
              </div>
              <div className="p-2 bg-muted rounded text-xs">
                <code>role: &apos;tenant_admin&apos;</code>
              </div>
              <Link href="/admin/tenant">
                <Button variant="outline" className="w-full" size="sm">
                  View Dashboard
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* C2Pro Admin */}
          <Card className="hover:shadow-lg transition-shadow">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-red-600" />
                <CardTitle>C2Pro Admin</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                System administrators with full platform access
              </p>
              <div className="space-y-2">
                <div className="text-sm">
                  <p className="font-medium">Permissions:</p>
                  <ul className="text-xs text-muted-foreground mt-1 space-y-1">
                    <li>✓ Manage tenants</li>
                    <li>✓ Manage all users</li>
                    <li>✓ System settings</li>
                    <li>✓ Billing</li>
                  </ul>
                </div>
              </div>
              <div className="p-2 bg-muted rounded text-xs">
                <code>role: &apos;c2pro_admin&apos;</code>
              </div>
              <Link href="/admin/c2pro">
                <Button variant="outline" className="w-full" size="sm">
                  View Dashboard
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        {/* Routes Overview */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Route Structure</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium mb-3">Public Routes</h4>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <code className="bg-muted px-2 py-1 rounded">/</code>
                    <span>Landing page</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <code className="bg-muted px-2 py-1 rounded">/login</code>
                    <span>Login</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <code className="bg-muted px-2 py-1 rounded">/signup</code>
                    <span>Registration</span>
                  </li>
                </ul>
              </div>

              <div>
                <h4 className="font-medium mb-3">Protected Routes</h4>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2">
                    <code className="bg-muted px-2 py-1 rounded">/dashboard</code>
                    <span>User projects</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <code className="bg-muted px-2 py-1 rounded">/admin/tenant</code>
                    <span>Tenant admin</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <code className="bg-muted px-2 py-1 rounded">/admin/c2pro</code>
                    <span>System admin</span>
                  </li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Testing Flow */}
        <Card>
          <CardHeader>
            <CardTitle>Test the Flow</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Start by creating an account or logging in to experience the role-based interface
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Link href="/signup" className="flex-1">
                <Button className="w-full gap-2">
                  Create Account
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link href="/login" className="flex-1">
                <Button variant="outline" className="w-full gap-2">
                  Login
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
              <Link href="/" className="flex-1">
                <Button variant="ghost" className="w-full gap-2">
                  Back Home
                  <ArrowRight className="w-4 h-4" />
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
