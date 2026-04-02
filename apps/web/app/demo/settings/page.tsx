"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  User,
  Bell,
  Shield,
  CreditCard,
  Users,
  Building2,
} from "lucide-react";

export default function DemoSettingsPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account and workspace preferences
        </p>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Settings are view-only in demo mode. Sign in to customize your
          workspace and account preferences.
        </p>
      </div>

      {/* Settings Sections */}
      <div className="space-y-6">
        {/* Profile Section */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <User className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-lg">Profile</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="name">Full Name</Label>
              <Input
                id="name"
                value="Demo User"
                disabled
                className="bg-slate-50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                value="demo@c2pro.app"
                disabled
                className="bg-slate-50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role">Role</Label>
              <Input
                id="role"
                value="Project Manager"
                disabled
                className="bg-slate-50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="timezone">Timezone</Label>
              <Input
                id="timezone"
                value="Europe/Madrid (UTC+1)"
                disabled
                className="bg-slate-50"
              />
            </div>
          </div>
        </Card>

        {/* Organization Section */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <Building2 className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-lg">Organization</h2>
            <Badge className="bg-yellow-100 text-yellow-700">Demo</Badge>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="org-name">Organization Name</Label>
              <Input
                id="org-name"
                value="Demo Workspace"
                disabled
                className="bg-slate-50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plan">Current Plan</Label>
              <Input
                id="plan"
                value="Demo (Read-Only)"
                disabled
                className="bg-slate-50"
              />
            </div>
          </div>
        </Card>

        {/* Notifications Section */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <Bell className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-lg">Notifications</h2>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-sm">Email Notifications</p>
                <p className="text-xs text-muted-foreground">
                  Receive alerts via email
                </p>
              </div>
              <Badge variant="outline">Enabled</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-sm">Critical Alerts</p>
                <p className="text-xs text-muted-foreground">
                  Immediate notification for critical issues
                </p>
              </div>
              <Badge variant="outline">Enabled</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-sm">Weekly Digest</p>
                <p className="text-xs text-muted-foreground">
                  Summary of project activity
                </p>
              </div>
              <Badge variant="outline">Enabled</Badge>
            </div>
          </div>
        </Card>

        {/* Security Section */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <Shield className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-lg">Security</h2>
          </div>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-sm">Two-Factor Authentication</p>
                <p className="text-xs text-muted-foreground">
                  Add an extra layer of security
                </p>
              </div>
              <Badge className="bg-green-100 text-green-700">Enabled</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div>
                <p className="font-medium text-sm">Session Timeout</p>
                <p className="text-xs text-muted-foreground">
                  Auto-logout after inactivity
                </p>
              </div>
              <Badge variant="outline">30 minutes</Badge>
            </div>
          </div>
        </Card>

        {/* Billing Section */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <CreditCard className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-lg">Billing & Plans</h2>
          </div>
          <div className="p-4 border border-dashed border-slate-300 rounded-lg text-center">
            <p className="text-muted-foreground mb-4">
              Billing features are not available in demo mode.
            </p>
            <Button disabled className="opacity-50">
              Upgrade Plan
            </Button>
          </div>
        </Card>

        {/* Team Section */}
        <Card className="p-6">
          <div className="flex items-center gap-3 mb-6">
            <Users className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-lg">Team Members</h2>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                  <span className="text-sm font-medium text-blue-700">DU</span>
                </div>
                <div>
                  <p className="font-medium text-sm">Demo User</p>
                  <p className="text-xs text-muted-foreground">demo@c2pro.app</p>
                </div>
              </div>
              <Badge>Owner</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                  <span className="text-sm font-medium text-green-700">SJ</span>
                </div>
                <div>
                  <p className="font-medium text-sm">Dr. Sarah Johnson</p>
                  <p className="text-xs text-muted-foreground">
                    sarah@techcore.com
                  </p>
                </div>
              </div>
              <Badge variant="outline">Admin</Badge>
            </div>
            <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
                  <span className="text-sm font-medium text-purple-700">MC</span>
                </div>
                <div>
                  <p className="font-medium text-sm">Michael Chen</p>
                  <p className="text-xs text-muted-foreground">
                    michael@supply.com
                  </p>
                </div>
              </div>
              <Badge variant="outline">Member</Badge>
            </div>
          </div>
          <div className="mt-4">
            <Button disabled className="opacity-50">
              Invite Team Member
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
