'use client';

import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Search, Users, Settings, LogOut } from 'lucide-react';
import { useState } from 'react';
import Link from 'next/link';

// Mock data for demonstration
const MOCK_PROJECTS = [
  {
    id: '1',
    name: 'Torre Skyline - Contract Review',
    status: 'active',
    coherence_score: 78,
    documents: 8,
    created_at: '2026-01-15',
  },
  {
    id: '2',
    name: 'Marina Development - Phase 2',
    status: 'active',
    coherence_score: 85,
    documents: 12,
    created_at: '2026-01-10',
  },
  {
    id: '3',
    name: 'Infrastructure Upgrade Project',
    status: 'completed',
    coherence_score: 92,
    documents: 15,
    created_at: '2025-12-20',
  },
];

export default function TenantAdminDashboard() {
  const { user, tenant, logout, userRole } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [projects] = useState(MOCK_PROJECTS);

  // Check if user has correct role
  if (userRole !== 'tenant_admin' && userRole !== 'c2pro_admin') {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold">Access Denied</h1>
          <p className="text-muted-foreground">You need Tenant Admin or C2Pro Admin access</p>
          <Link href="/">
            <Button>Go Home</Button>
          </Link>
        </div>
      </div>
    );
  }

  const filteredProjects = projects.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <ProtectedRoute requiredRole="tenant_admin">
      <div className="min-h-screen bg-background">
        {/* Header */}
        <header className="border-b bg-card">
          <div className="max-w-7xl mx-auto px-4 py-6 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Tenant Admin</h1>
              <p className="text-sm text-muted-foreground">{tenant?.name}</p>
            </div>
            <div className="flex items-center gap-4">
              <Link href="/admin/tenant/users">
                <Button variant="outline" size="sm" className="gap-2">
                  <Users className="w-4 h-4" />
                  Manage Users
                </Button>
              </Link>
              <Link href="/admin/tenant/settings">
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
                  Total Projects
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{projects.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Active Projects
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {projects.filter(p => p.status === 'active').length}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Documents
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {projects.reduce((sum, p) => sum + p.documents, 0)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Avg Coherence
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {Math.round(projects.reduce((sum, p) => sum + p.coherence_score, 0) / projects.length)}%
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Projects Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-foreground">Projects</h2>
              <Link href="/dashboard/projects/new">
                <Button className="gap-2">
                  <Plus className="w-4 h-4" />
                  New Project
                </Button>
              </Link>
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search projects..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Projects Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProjects.map(project => (
                <Link key={project.id} href={`/dashboard/projects/${project.id}`}>
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <CardHeader>
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-base line-clamp-2">
                          {project.name}
                        </CardTitle>
                        <span className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
                          project.status === 'active'
                            ? 'bg-green-500/10 text-green-600'
                            : 'bg-gray-500/10 text-gray-600'
                        }`}>
                          {project.status}
                        </span>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">Coherence Score</span>
                          <span className="text-sm font-bold text-primary">
                            {project.coherence_score}%
                          </span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2">
                          <div
                            className="bg-primary h-2 rounded-full transition-all"
                            style={{ width: `${project.coherence_score}%` }}
                          />
                        </div>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {project.documents} documents
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>

            {filteredProjects.length === 0 && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No projects found</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
