import Link from "next/link";
import type { ReactNode } from "react";
import {
  LayoutDashboard,
  Gauge,
  FileText,
  AlertTriangle,
  Users,
  ShoppingCart,
  Settings,
} from 'lucide-react';

const tabs = [
  { href: '', label: 'Overview', icon: LayoutDashboard },
  { href: '/coherence', label: 'Coherence', icon: Gauge },
  { href: '/documents', label: 'Documents', icon: FileText },
  { href: '/evidence', label: 'Evidence', icon: Gauge },
  { href: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { href: '/stakeholders', label: 'Stakeholders', icon: Users },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default async function ProjectLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <section className="space-y-5">
      <div className="rounded-md border bg-card p-4">
        <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          Project
        </div>
        <h2 className="text-lg font-semibold">{id}</h2>
        <nav className="mt-3 flex flex-wrap gap-1" aria-label="Project tabs">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <Link
                key={tab.href}
                href={`/projects/${id}${tab.href}`}
                className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/30 hover:bg-accent hover:text-foreground"
              >
                <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
                {tab.label}
              </Link>
            );
          })}
        </nav>
      </div>
      {children}
    </section>
  );
}
