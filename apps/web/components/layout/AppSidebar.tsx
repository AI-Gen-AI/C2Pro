'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useOrganization } from '@clerk/nextjs';
import { env } from '@/config/env';
import {
  LayoutDashboard,
  FolderKanban,
  AlertTriangle,
  Users,
  ChevronLeft,
  ChevronRight,
  Gauge,
  Grid3X3,
  LineChart,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSidebarStore } from '@/stores/sidebar';
import { useEffect } from 'react';

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string;
};

const navItems: NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/projects', label: 'Projects', icon: FolderKanban },
  { href: '/evidence', label: 'Evidence', icon: Gauge },
  { href: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { href: '/stakeholders', label: 'Stakeholders', icon: Users },
  { href: '/ai-analytics', label: 'AI Analytics', icon: LineChart },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { organization } = useOrganization();
  const { isCollapsed, toggle, setCollapsed } = useSidebarStore();

  // Handle initial mobile state - collapse by default on small screens
  useEffect(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      setCollapsed(true);
    }
  }, [setCollapsed]);

  // Check if we're in demo mode based on the current path
  const isDemoMode = pathname.startsWith('/demo');
  const basePrefix = isDemoMode ? '/demo' : '';
  const workspaceLabel = isDemoMode ? 'Demo Workspace' : organization?.name ?? 'Workspace';
  const visibleNavItems = env.FEATURE_RACI_GENERATION
    ? [...navItems, { href: '/raci', label: 'RACI Matrix', icon: Grid3X3 }]
    : navItems;

  const getHref = (href: string) => {
    if (href === '/dashboard') {
      return isDemoMode ? '/demo' : '/';
    }
    return `${basePrefix}${href}`;
  };

  const isActive = (href: string) => {
    const fullHref = getHref(href);
    if (href === '/dashboard') {
      return isDemoMode
        ? pathname === '/demo'
        : pathname === '/' || pathname === '/dashboard';
    }
    return pathname.startsWith(fullHref);
  };

  return (
    <aside
      aria-label="Application sidebar"
      className={cn(
        'fixed inset-y-0 left-0 z-50 flex flex-col bg-sidebar transition-all duration-300 md:relative',
        isCollapsed ? 'w-0 -translate-x-full md:w-14 md:translate-x-0' : 'w-[210px] translate-x-0'
      )}
    >
      {/* Overlay for mobile when sidebar is open */}
      {!isCollapsed && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm md:hidden" 
          onClick={() => setCollapsed(true)}
        />
      )}

      <div className="relative flex h-full flex-col bg-sidebar overflow-hidden">
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-primary to-[hsl(187,100%,28%)]">
            <span className="font-mono text-xs font-bold text-primary-foreground">C2</span>
          </div>
          {!isCollapsed && (
            <span className="font-mono text-sm font-semibold tracking-tight text-sidebar-foreground">
              C2Pro
            </span>
          )}
        </div>

        {/* Project Context */}
        {!isCollapsed && (
          <div className="px-4 pb-3">
            <span className="text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">
              {workspaceLabel}
            </span>
            {isDemoMode ? (
              <p className="mt-1 text-[11px] font-medium text-warning">
                Sample data only
              </p>
            ) : null}
          </div>
        )}

        {/* Navigation */}
        <nav
          id="primary-navigation"
          className="flex-1 space-y-0.5 px-0"
          aria-label="Primary"
        >
          {visibleNavItems.map((item: NavItem) => {
            const active = isActive(item.href);
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={getHref(item.href)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 text-[13px] transition-all duration-150',
                  'border-l-[3px]',
                  active
                    ? 'border-sidebar-primary bg-sidebar-accent font-semibold text-sidebar-foreground'
                    : 'border-transparent text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
                )}
                onClick={() => {
                  if (typeof window !== 'undefined' && window.innerWidth < 768) {
                    setCollapsed(true);
                  }
                }}
              >
                <Icon className="h-4 w-4 shrink-0" strokeWidth={active ? 2 : 1.5} />
                {!isCollapsed && (
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
        <div className="mt-auto border-t border-sidebar-border p-2">
          <Link
            href={`${basePrefix}/settings`}
            className={cn(
              'flex items-center gap-2 rounded-md px-3 py-2 text-[13px] text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/50 hover:text-sidebar-foreground'
            )}
            onClick={() => {
              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                setCollapsed(true);
              }
            }}
          >
            <Settings className="h-4 w-4 shrink-0" strokeWidth={1.5} />
            {!isCollapsed && <span>Settings</span>}
          </Link>

          <button
            className="mt-1 hidden md:flex w-full items-center justify-center rounded-md py-1.5 text-sidebar-foreground/50 transition-colors hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
            onClick={toggle}
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-controls="primary-navigation"
            aria-expanded={!isCollapsed}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </aside>
  );
}
