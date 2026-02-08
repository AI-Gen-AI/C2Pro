'use client';

import { useAuth } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { ArrowLeft, LogOut } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

export default function TenantSettingsPage() {
  const { tenant, logout } = useAuth();
  const [formData, setFormData] = useState({
    company_name: tenant?.name || '',
    subscription_plan: tenant?.subscription_plan || 'professional',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.currentTarget;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = () => {
    // TODO: Implement save logic
    console.log('Saving settings:', formData);
  };

  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-background">
        {/* Header */}
        <header className="border-b bg-card">
          <div className="max-w-4xl mx-auto px-4 py-6">
            <Link href="/admin/tenant" className="inline-flex items-center gap-2 text-primary hover:text-primary/80 mb-4">
              <ArrowLeft className="w-4 h-4" />
              Back to Dashboard
            </Link>
            <div className="flex items-center justify-between">
              <h1 className="text-2xl font-bold text-foreground">Tenant Settings</h1>
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
        <main className="max-w-4xl mx-auto px-4 py-8">
          <div className="space-y-6">
            {/* Basic Information */}
            <Card>
              <CardHeader>
                <CardTitle>Company Information</CardTitle>
                <CardDescription>
                  Manage your tenant's basic information
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="company_name">Company Name</Label>
                  <Input
                    id="company_name"
                    name="company_name"
                    value={formData.company_name}
                    onChange={handleChange}
                    placeholder="Your company name"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="subscription_plan">Subscription Plan</Label>
                  <select
                    id="subscription_plan"
                    name="subscription_plan"
                    value={formData.subscription_plan}
                    onChange={handleChange}
                    className="w-full px-3 py-2 border border-input rounded-md bg-background text-foreground"
                  >
                    <option value="starter">Starter</option>
                    <option value="professional">Professional</option>
                    <option value="enterprise">Enterprise</option>
                  </select>
                </div>

                <Button onClick={handleSave} className="mt-4">
                  Save Changes
                </Button>
              </CardContent>
            </Card>

            {/* Billing Information */}
            <Card>
              <CardHeader>
                <CardTitle>Billing Information</CardTitle>
                <CardDescription>
                  Manage your billing and subscription
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">Current Plan</p>
                    <p className="text-lg font-semibold capitalize">{formData.subscription_plan}</p>
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm text-muted-foreground">Billing Cycle</p>
                    <p className="text-lg font-semibold">Monthly</p>
                  </div>
                </div>

                <Button variant="outline" className="w-full">
                  Manage Billing
                </Button>
              </CardContent>
            </Card>

            {/* Danger Zone */}
            <Card className="border-destructive/50">
              <CardHeader>
                <CardTitle className="text-destructive">Danger Zone</CardTitle>
                <CardDescription>
                  Irreversible actions. Proceed with caution.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Delete Tenant</p>
                    <p className="text-sm text-muted-foreground">
                      Permanently delete this tenant and all associated data
                    </p>
                  </div>
                  <Button variant="destructive">
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
