"use client";

import { env } from "@/config/env";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  ClipboardCheck,
  FileText,
  Gauge,
  LayoutDashboard,
  ScrollText,
  Settings,
  Users,
  ListTree,
} from "lucide-react";

const tabs = [
  { href: "", label: "Overview", icon: LayoutDashboard },
  { href: "/coherence", label: "Coherence", icon: Gauge },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/evidence", label: "Evidence", icon: Gauge },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle },
  { href: "/review", label: "Review", icon: ClipboardCheck },
  { href: "/stakeholders", label: "Stakeholders", icon: Users },
  { href: "/wbs", label: "WBS", icon: ListTree },
  { href: "/budget", label: "Budget", icon: Gauge },
  { href: "/report", label: "Report", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
];

interface ProjectTabsProps {
  projectId: string;
}

export function ProjectTabs({ projectId }: ProjectTabsProps) {
  const pathname = usePathname() || "";

  return (
    <nav className="mt-3 flex flex-wrap gap-1" aria-label="Project tabs">
      {tabs.filter(tab => {
        if (tab.href === "/stakeholders" || tab.href === "/wbs") {
          return env.FEATURE_PHASE2_MODULES;
        }
        return true;
      }).map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.href === "" 
          ? pathname === `/projects/${projectId}` || pathname === `/projects/${projectId}/`
          : pathname.endsWith(tab.href) || pathname.includes(`${tab.href}/`);

        return (
          <Link
            key={tab.href}
            href={`/projects/${projectId}${tab.href}`}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium transition-colors",
              isActive 
                ? "bg-slate-900 text-white border-slate-900" 
                : "text-muted-foreground hover:border-primary/30 hover:bg-accent hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
