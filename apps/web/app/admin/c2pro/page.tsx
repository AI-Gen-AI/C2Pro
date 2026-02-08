'use client';

import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Search, Settings, LogOut, Building2, Users } from 'lucide-react';
import { useState } from 'react';
import Link from 'next/link';

// Mock data
const MOCK_TENANTS = [
  {
    id: '1',
    name: 'Construcciones García',
    subscription_plan: 'enterprise',
    users: 8,
    projects: 3,
    status: 'active',
    created_at: '2025-11-15',
  },
  {
    id: '2',
    name: 'Ingeniería Constructiva',
    subscription_plan: 'professional',
    users: 5,
    projects: 2,
    status: 'active',
    created_at: '2025-12-01',
  },
  {
    id: '3',
    name: 'Development Solutions',
    subscription_plan: 'starter',
    users: 2,
    projects: 1,
    status: 'active',
    created_at: '2026-01-10',
  },
];

export default function C2ProAdminPanel() {
  const { logout, userRole } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [tenants] = useState(MOCK_TENANTS);

  // Check if user has correct role
  if (userRole !== 'c2pro_admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold">Access Denied</h1>
          <p className="text-muted-foreground">Only C2Pro Admin can access this page</p>
          <Link href="/">
            <Button>Go Home</Button>
          </Link>
        </div>
      </div>
    );
  }

  const filteredTenants = tenants.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getPlanColor = (plan: string) => {
    switch (plan) {
      case 'enterprise':
        return 'bg-purple-500/10 text-purple-600';
      case 'professional':
        return 'bg-blue-500/10 text-blue-600';
      default:
        return 'bg-gray-500/10 text-gray-600';
    }
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background">
        {/* Header */}
        <header className="border-b bg-card">
          <div className="max-w-7xl mx-auto px-4 py-6 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">C2Pro Admin</h1>
              <p className="text-sm text-muted-foreground">System Administration</p>
            </div>
            <div className="flex items-center gap-4">
              <Link href="/admin/c2pro/settings">
                <Button variant="outline" size="sm" className="gap-2">
                  <Settings className="w-4 h-4" />
                  Settings
                </Button>
              </Link>
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                className="gap-2"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </Button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 py-8">
          {/* Stats */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Tenants
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{tenants.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Active Tenants
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {tenants.filter(t => t.status === 'active').length}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Users
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {tenants.reduce((sum, t) => sum + t.users, 0)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Projects
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {tenants.reduce((sum, t) => sum + t.projects, 0)}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Tenants Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-foreground">Tenants</h2>
              <Button className="gap-2">
                <Plus className="w-4 h-4" />
                Add Tenant
              </Button>
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search tenants..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Tenants Table */}
            <Card>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b bg-muted/50">
                    <tr className="text-sm">
                      <th className="px-6 py-3 text-left font-medium">Tenant Name</th>
                      <th className="px-6 py-3 text-left font-medium">Plan</th>
                      <th className="px-6 py-3 text-left font-medium">Users</th>
                      <th className="px-6 py-3 text-left font-medium">Projects</th>
                      <th className="px-6 py-3 text-left font-medium">Status</th>
                      <th className="px-6 py-3 text-left font-medium">Created</th>
                      <th className="px-6 py-3 text-left font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTenants.map(tenant => (
                      <tr key={tenant.id} className="border-b hover:bg-muted/50 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <Building2 className="w-4 h-4 text-muted-foreground" />
                            <span className="font-medium">{tenant.name}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getPlanColor(tenant.subscription_plan)}`}>
                            {tenant.subscription_plan}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-1">
                            <Users className="w-4 h-4 text-muted-foreground" />
                            {tenant.users}
                          </div>
                        </td>
                        <td className="px-6 py-4">{tenant.projects}</td>
                        <td className="px-6 py-4">
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-600">
                            {tenant.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-muted-foreground">
                          {new Date(tenant.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4">
                          <Button variant="outline" size="sm">
                            View
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredTenants.length === 0 && (
                <div className="text-center py-12">
                  <p className="text-muted-foreground">No tenants found</p>
                </div>
              )}
            </Card>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
