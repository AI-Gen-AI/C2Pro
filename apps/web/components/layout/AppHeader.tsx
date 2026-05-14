'use client';

import { Bell, LogOut, Search, User, Menu } from 'lucide-react';
import { useClerk, useUser } from '@clerk/nextjs';
import { usePathname } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import {
  useAppModeStore,
  selectIsDemoMode,
  isExplicitDemoRoute,
} from '@/stores/app-mode';
import { useSidebarStore } from '@/stores/sidebar';

interface AppHeaderProps {
  title?: string;
  breadcrumb?: string[];
}

export function AppHeader({ title = 'Dashboard', breadcrumb }: AppHeaderProps) {
  const { signOut } = useClerk();
  const { user } = useUser();
  const pathname = usePathname();
  const { toggle } = useSidebarStore();
  
  const demoEnvironmentEnabled = useAppModeStore(
    (state) => state.demoEnvironmentEnabled,
  );
  const isDemoInStore = useAppModeStore(selectIsDemoMode);
  const isDemoMode = demoEnvironmentEnabled && (isDemoInStore || isExplicitDemoRoute(pathname));

  const handleSignOut = () => {
    signOut({ redirectUrl: '/sign-in' });
  };

  const userInitials = user?.firstName && user?.lastName
    ? `${user.firstName[0]}${user.lastName[0]}`
    : user?.emailAddresses?.[0]?.emailAddress?.substring(0, 2).toUpperCase() || 'U';

  const userName = user?.fullName || user?.emailAddresses?.[0]?.emailAddress || 'User';
  const userEmail = user?.emailAddresses?.[0]?.emailAddress || '';
  const notificationCount = isDemoMode ? 3 : 0;

  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b bg-card px-6">
      {/* Left: Menu Toggle (Mobile) + Breadcrumb / Title */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={toggle}
          aria-label="Toggle Menu"
        >
          <Menu className="h-5 w-5" />
        </Button>

        {breadcrumb && breadcrumb.length > 0 ? (
          <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
            {breadcrumb.map((item, index) => (
              <span key={index} className="flex items-center gap-2">
                {index > 0 && <span className="text-muted-foreground">/</span>}
                <span
                  className={
                    index === breadcrumb.length - 1
                      ? 'font-medium text-foreground'
                      : 'text-muted-foreground hover:text-foreground cursor-pointer'
                  }
                >
                  {item}
                </span>
              </span>
            ))}
          </nav>
        ) : (
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{title}</h1>
            {isDemoMode ? (
              <>
                <Badge
                  variant="outline"
                  className="border-warning/40 bg-warning-bg text-warning"
                >
                  Demo Workspace
                </Badge>
                <Badge
                  variant="outline"
                  className="hidden border-warning/30 text-warning md:inline-flex"
                >
                  Sample Data
                </Badge>
              </>
            ) : null}
          </div>
        )}
      </div>

      {/* Right: Search, Notifications, Avatar */}
      <div className="flex items-center gap-4">
        <div className="relative hidden lg:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search..."
            className="w-64 pl-9"
            aria-label="Search"
          />
        </div>

        <ThemeToggle />

        {/* Notifications */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="relative"
              aria-label="Notifications"
            >
              <Bell className="h-5 w-5" />
              {notificationCount > 0 ? (
                <Badge
                  variant="destructive"
                  className="absolute -right-1 -top-1 h-5 w-5 rounded-full p-0 text-xs animate-pulse-critical"
                >
                  {notificationCount}
                </Badge>
              ) : null}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            sideOffset={10}
            className="w-80 rounded-2xl border-border/80 bg-background/95 p-2 shadow-2xl backdrop-blur-md"
          >
            <DropdownMenuLabel className="rounded-xl border bg-muted/40 px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex flex-col">
                  <span className="font-semibold text-foreground">Notifications</span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {isDemoMode
                      ? 'Sample workspace activity feed'
                      : 'Workspace alerts and events will appear here'}
                  </span>
                </div>
                {notificationCount > 0 ? (
                  <Badge variant="destructive" className="rounded-full px-2 py-0.5 text-[11px]">
                    {notificationCount} new
                  </Badge>
                ) : null}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            {isDemoMode ? (
              <>
                <DropdownMenuItem className="flex flex-col items-start gap-1 rounded-xl px-3 py-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="destructive" className="text-xs">Critical</Badge>
                    <span className="text-sm font-medium">New alert raised</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Contract Penalty Clause Violation Risk - 2 hours ago
                  </span>
                </DropdownMenuItem>
                <DropdownMenuItem className="flex flex-col items-start gap-1 rounded-xl px-3 py-3">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">Update</Badge>
                    <span className="text-sm font-medium">Score changed</span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    PROJ-001 coherence score: 76 → 78 - 1 day ago
                  </span>
                </DropdownMenuItem>
              </>
            ) : (
              <DropdownMenuItem
                disabled
                className="flex flex-col items-start gap-1 rounded-xl border bg-muted/30 px-3 py-3 opacity-100"
              >
                <span className="text-sm font-medium">No new notifications</span>
                <span className="text-xs text-muted-foreground">
                  Live workspace notifications will appear here once alerts and events are generated.
                </span>
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem className="justify-center rounded-xl px-3 py-2.5 text-sm text-primary">
              View all notifications
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        {/* User Avatar */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full"
              aria-label="User menu"
            >
              <Avatar className="h-8 w-8">
                <AvatarImage src={user?.imageUrl} />
                <AvatarFallback className="bg-primary text-primary-foreground text-sm">
                  {userInitials}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            sideOffset={10}
            className="w-64 rounded-2xl border-border/80 bg-background/95 p-2 shadow-2xl backdrop-blur-md"
          >
            <DropdownMenuLabel className="flex flex-col rounded-xl border bg-muted/40 px-3 py-3">
              <span className="font-semibold text-foreground">{userName}</span>
              <span className="text-xs font-normal text-muted-foreground">
                {userEmail}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="rounded-xl px-3 py-2.5">
              <User className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem className="rounded-xl px-3 py-2.5">
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="rounded-xl px-3 py-2.5 text-destructive focus:bg-destructive/10 focus:text-destructive"
              onClick={handleSignOut}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
