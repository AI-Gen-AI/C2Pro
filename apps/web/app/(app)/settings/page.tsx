'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { User, Bell, Shield, Database } from 'lucide-react';
import {
  useGetMeApiV1AuthMeGet,
  useUpdateMeApiV1AuthMePut,
} from '@/lib/api/generated/authentication/authentication';

/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Settings page uses generated auth profile endpoints.
 */
export default function SettingsPage() {
  const { data, isLoading, error } = useGetMeApiV1AuthMeGet();
  const updateMe = useUpdateMeApiV1AuthMePut();
  const profile = ((data as { user?: {
    email?: string | null;
    first_name?: string | null;
    last_name?: string | null;
    phone?: string | null;
    role?: string | null;
  }; tenant?: { name?: string | null } } | undefined)?.user
    ? (data as {
        user?: {
          email?: string | null;
          first_name?: string | null;
          last_name?: string | null;
          phone?: string | null;
          role?: string | null;
        };
        tenant?: { name?: string | null };
      })
    : (data as { data?: {
        user?: {
          email?: string | null;
          first_name?: string | null;
          last_name?: string | null;
          phone?: string | null;
          role?: string | null;
        };
        tenant?: { name?: string | null };
      } } | undefined)?.data) ?? { user: undefined, tenant: undefined };

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [criticalAlerts, setCriticalAlerts] = useState(true);
  const [weeklyReports, setWeeklyReports] = useState(false);
  const [language, setLanguage] = useState('en');
  const [timezone, setTimezone] = useState('utc');
  const [dateFormat, setDateFormat] = useState('mdy');
  const [phone, setPhone] = useState('');
  const [profileSaved, setProfileSaved] = useState(false);
  const [profileErrors, setProfileErrors] = useState<{
    firstName?: string;
    phone?: string;
  }>({});

  useEffect(() => {
    if (!profile.user) {
      return;
    }

    setFirstName(profile.user.first_name ?? '');
    setLastName(profile.user.last_name ?? '');
    setPhone(profile.user.phone ?? '');
  }, [profile.user?.first_name, profile.user?.last_name, profile.user?.phone]);

  const validateProfile = () => {
    const nextErrors: {
      firstName?: string;
      phone?: string;
    } = {};

    if (!firstName.trim()) {
      nextErrors.firstName = 'First name is required';
    }

    if (phone.trim() && !/^[+\d\s()-]{7,}$/.test(phone.trim())) {
      nextErrors.phone = 'Enter a valid phone number';
    }

    setProfileErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const handleSaveProfile = async () => {
    setProfileSaved(false);
    if (!validateProfile()) {
      return;
    }

    await updateMe.mutateAsync({
      data: {
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        phone: phone.trim() || null,
        preferences: {
          email_notifications: emailNotifications,
          critical_alerts: criticalAlerts,
          weekly_reports: weeklyReports,
          language,
          timezone,
          date_format: dateFormat,
        },
      },
    });
    setProfileSaved(true);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account settings and preferences
        </p>
      </div>

      <Tabs defaultValue="profile" className="space-y-6">
        <TabsList>
          <TabsTrigger value="profile">
            <User className="mr-2 h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="mr-2 h-4 w-4" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="security">
            <Shield className="mr-2 h-4 w-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="system">
            <Database className="mr-2 h-4 w-4" />
            System
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="space-y-6">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Profile Information</h2>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">Loading profile...</p>
            ) : error ? (
              <p className="text-sm text-destructive">
                {error instanceof Error ? error.message : 'Failed to load profile'}
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="first-name">First Name</Label>
                  <Input
                    id="first-name"
                    value={firstName}
                    onChange={(event) => {
                      setFirstName(event.target.value);
                      setProfileErrors((current) => ({ ...current, firstName: undefined }));
                    }}
                    placeholder="John"
                  />
                  {profileErrors.firstName ? (
                    <p className="text-sm text-destructive">{profileErrors.firstName}</p>
                  ) : null}
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="last-name">Last Name</Label>
                  <Input
                    id="last-name"
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                    placeholder="Doe"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    value={profile.user?.email ?? ''}
                    readOnly
                    type="email"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="phone">Phone</Label>
                  <Input
                    id="phone"
                    value={phone}
                    onChange={(event) => {
                      setPhone(event.target.value);
                      setProfileErrors((current) => ({ ...current, phone: undefined }));
                    }}
                    placeholder="+1 555 000 000"
                  />
                  {profileErrors.phone ? (
                    <p className="text-sm text-destructive">{profileErrors.phone}</p>
                  ) : null}
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="role">Role</Label>
                  <Input id="role" value={profile.user?.role ?? ''} readOnly />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="company">Company</Label>
                  <Input
                    id="company"
                    value={profile.tenant?.name ?? ''}
                    readOnly
                    placeholder="Acme Corp"
                  />
                </div>
                <Button onClick={handleSaveProfile} disabled={updateMe.isPending}>
                  Save Profile Changes
                </Button>
                {profileSaved ? (
                  <p className="text-sm text-muted-foreground">Profile saved.</p>
                ) : null}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">
              Notification Preferences
            </h2>
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Email Notifications</Label>
                  <p className="text-sm text-muted-foreground">
                    Receive email notifications for important events
                  </p>
                </div>
                <Switch
                  checked={emailNotifications}
                  onCheckedChange={setEmailNotifications}
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Critical Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Get notified immediately for critical alerts
                  </p>
                </div>
                <Switch
                  checked={criticalAlerts}
                  onCheckedChange={setCriticalAlerts}
                />
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Weekly Reports</Label>
                  <p className="text-sm text-muted-foreground">
                    Receive weekly project summary reports
                  </p>
                </div>
                <Switch
                  checked={weeklyReports}
                  onCheckedChange={setWeeklyReports}
                />
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="security" className="space-y-6">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">Security Settings</h2>
            <div className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="current-password">Current Password</Label>
                <Input id="current-password" type="password" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="new-password">New Password</Label>
                <Input id="new-password" type="password" />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="confirm-password">Confirm New Password</Label>
                <Input id="confirm-password" type="password" />
              </div>
              <Button>Update Password</Button>
            </div>
          </div>

          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">
              Two-Factor Authentication
            </h2>
            <p className="mb-4 text-sm text-muted-foreground">
              Add an extra layer of security to your account
            </p>
            <Button variant="outline">Enable 2FA</Button>
          </div>
        </TabsContent>

        <TabsContent value="system" className="space-y-6">
          <div className="rounded-lg border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold">System Preferences</h2>
            <div className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="language">Language</Label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="es">Spanish</SelectItem>
                    <SelectItem value="fr">Français</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="timezone">Timezone</Label>
                <Select value={timezone} onValueChange={setTimezone}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="utc">UTC</SelectItem>
                    <SelectItem value="est">Eastern Time</SelectItem>
                    <SelectItem value="pst">Pacific Time</SelectItem>
                    <SelectItem value="cet">Central European Time</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="date-format">Date Format</Label>
                <Select value={dateFormat} onValueChange={setDateFormat}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mdy">MM/DD/YYYY</SelectItem>
                    <SelectItem value="dmy">DD/MM/YYYY</SelectItem>
                    <SelectItem value="ymd">YYYY-MM-DD</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={handleSaveProfile} disabled={updateMe.isPending}>
                Save Preferences
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
