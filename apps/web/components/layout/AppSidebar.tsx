'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  AlertTriangle,
  Users,
  ShoppingCart,
  Settings,
  ChevronLeft,
  ChevronRight,
  Gauge,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/projects', label: 'Projects', icon: FolderKanban },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/alerts', label: 'Alerts', icon: AlertTriangle, badge: 15 },
  { href: '/stakeholders', label: 'Stakeholders', icon: Users },
  { href: '/evidence', label: 'Evidence', icon: Gauge },
];

export function AppSidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  const isActive = (href: string) => {
    if (href === '/') return pathname === '/';
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={cn(
        'flex h-full flex-col bg-sidebar transition-all duration-300 shrink-0',
        collapsed ? 'w-14' : 'w-[210px]'
      )}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-4">
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-primary to-[hsl(187,100%,28%)]">
          <span className="font-mono text-xs font-bold text-primary-foreground">C2</span>
        </div>
        {!collapsed && (
          <span className="font-mono text-sm font-semibold tracking-tight text-sidebar-foreground">
            C2Pro
          </span>
        )}
      </div>

      {/* Project Context */}
      {!collapsed && (
        <div className="px-4 pb-3">
          <span className="text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">
            Torre Skyline
          </span>
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 px-0" aria-label="Primary">
        {navItems.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                'flex items-center gap-2 px-4 py-2 text-[13px] transition-all duration-150',
                'border-l-[3px]',
                active
                  ? 'border-sidebar-primary bg-sidebar-accent font-medium text-white'
                  : 'border-transparent text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={active ? 2 : 1.5} />
              {!collapsed && (
                <>
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-auto rounded-full bg-destructive px-1.5 py-px font-mono text-[10px] font-semibold text-destructive-foreground">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-sidebar-border p-2">
        <Link
          href="/settings"
          className={cn(
            'flex items-center gap-2 rounded-md px-3 py-2 text-[13px] text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
          )}
        >
          <Settings className="h-4 w-4 shrink-0" strokeWidth={1.5} />
          {!collapsed && <span>Settings</span>}
        </Link>

        <button
          className="mt-1 flex w-full items-center justify-center rounded-md py-1.5 text-sidebar-foreground/50 transition-colors hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
