'use client';

import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Search, Edit2, Trash2, ArrowLeft, Mail } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

const MOCK_USERS = [
  {
    id: '1',
    email: 'admin@example.com',
    first_name: 'Admin',
    last_name: 'User',
    role: 'tenant_admin',
    status: 'active',
    created_at: '2025-11-15',
  },
  {
    id: '2',
    email: 'engineer1@example.com',
    first_name: 'Carlos',
    last_name: 'García',
    role: 'user',
    status: 'active',
    created_at: '2025-12-01',
  },
  {
    id: '3',
    email: 'engineer2@example.com',
    first_name: 'María',
    last_name: 'López',
    role: 'user',
    status: 'active',
    created_at: '2026-01-05',
  },
];

export default function ManageUsersPage() {
  const { logout } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [users] = useState(MOCK_USERS);

  const filteredUsers = users.filter(u =>
    u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    `${u.first_name} ${u.last_name}`.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'tenant_admin':
        return 'bg-purple-500/10 text-purple-600';
      case 'user':
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
          <div className="max-w-7xl mx-auto px-4 py-6">
            <Link href="/admin/tenant" className="inline-flex items-center gap-2 text-primary hover:text-primary/80 mb-4">
              <ArrowLeft className="w-4 h-4" />
              Back to Dashboard
            </Link>
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold text-foreground">Manage Users</h1>
              <div className="flex items-center gap-4">
                <Button className="gap-2">
                  <Plus className="w-4 h-4" />
                  Invite User
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={logout}
                  className="gap-2"
                >
                  Logout
                </Button>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 py-8">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Total Users
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">{users.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Active Users
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {users.filter(u => u.status === 'active').length}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Admins
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold">
                  {users.filter(u => u.role === 'tenant_admin').length}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Search */}
          <div className="relative mb-6">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search users by name or email..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Users Table */}
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b bg-muted/50">
                  <tr className="text-sm">
                    <th className="px-6 py-3 text-left font-medium">Name</th>
                    <th className="px-6 py-3 text-left font-medium">Email</th>
                    <th className="px-6 py-3 text-left font-medium">Role</th>
                    <th className="px-6 py-3 text-left font-medium">Status</th>
                    <th className="px-6 py-3 text-left font-medium">Joined</th>
                    <th className="px-6 py-3 text-left font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map(user => (
                    <tr key={user.id} className="border-b hover:bg-muted/50 transition-colors">
                      <td className="px-6 py-4 font-medium">
                        {user.first_name} {user.last_name}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Mail className="w-4 h-4 text-muted-foreground" />
                          {user.email}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${getRoleColor(user.role)}`}>
                          {user.role === 'tenant_admin' ? 'Admin' : 'User'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-600">
                          {user.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-muted-foreground">
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 flex gap-2">
                        <Button variant="outline" size="sm">
                          <Edit2 className="w-4 h-4" />
                        </Button>
                        <Button variant="outline" size="sm">
                          <Trash2 className="w-4 h-4 text-destructive" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {filteredUsers.length === 0 && (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No users found</p>
              </div>
            )}
          </Card>
        </main>
      </div>
    </ProtectedRoute>
  );
}
