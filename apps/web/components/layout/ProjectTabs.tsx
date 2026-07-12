import { env } from "@/config/env";
import Link from "next/link";
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
  return (
    <nav className="mt-3 flex flex-wrap gap-1" aria-label="Project tabs">
      {tabs.filter(tab => {
        if (tab.href === "/stakeholders" || tab.href === "/wbs") {
          return env.FEATURE_PHASE2_MODULES;
        }
        return true;
      }).map((tab) => {
        const Icon = tab.icon;
        return (
          <Link
            key={tab.href}
            href={`/projects/${projectId}${tab.href}`}
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/30 hover:bg-accent hover:text-foreground"
          >
            <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
