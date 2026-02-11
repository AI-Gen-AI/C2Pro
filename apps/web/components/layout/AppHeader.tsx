'use client';

import { Bell, Search, User } from 'lucide-react';
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

interface AppHeaderProps {
  title?: string;
  breadcrumb?: string[];
}

export function AppHeader({ title = 'Dashboard', breadcrumb }: AppHeaderProps) {
  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b bg-card px-6">
      {/* Left: Breadcrumb / Title */}
      <div className="flex items-center gap-2">
        {breadcrumb && breadcrumb.length > 0 ? (
          <nav className="flex items-center gap-2 text-sm">
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
          <h1 className="text-xl font-semibold">{title}</h1>
        )}
      </div>

      {/* Right: Search, Notifications, Avatar */}
      <div className="flex items-center gap-4">
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search..."
            className="w-64 pl-9"
            aria-label="Search"
          />
        </div>

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
              <Badge
                variant="destructive"
                className="absolute -right-1 -top-1 h-5 w-5 rounded-full p-0 text-xs animate-pulse-critical"
              >
                3
              </Badge>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80">
            <DropdownMenuLabel>Notifications</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="flex flex-col items-start gap-1 py-3">
              <div className="flex items-center gap-2">
                <Badge variant="destructive" className="text-xs">Critical</Badge>
                <span className="text-sm font-medium">New alert raised</span>
              </div>
              <span className="text-xs text-muted-foreground">
                Contract Penalty Clause Violation Risk - 2 hours ago
              </span>
            </DropdownMenuItem>
            <DropdownMenuItem className="flex flex-col items-start gap-1 py-3">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">Update</Badge>
                <span className="text-sm font-medium">Score changed</span>
              </div>
              <span className="text-xs text-muted-foreground">
                PROJ-001 coherence score: 76 → 78 - 1 day ago
              </span>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="justify-center text-sm text-primary">
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
                <AvatarImage src="" />
                <AvatarFallback className="bg-primary text-primary-foreground text-sm">
                  JD
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col">
              <span>John Doe</span>
              <span className="text-xs font-normal text-muted-foreground">
                john.doe@company.com
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>
              <User className="mr-2 h-4 w-4" />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem>Settings</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem className="text-destructive">Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
