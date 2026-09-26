/**
 * Test Suite ID: TS-P0D-REPORT-UI-003
 * Project Report route: current state report (default) and the audit export.
 * The selected mode lives only in `?mode=`, so either view can be linked to directly
 * and the tab always matches the URL, including back/forward and in-app links.
 */
"use client";

import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { AuditReportMode } from "@/components/features/report/AuditReportMode";
import { CurrentStateReportMode } from "@/components/features/report/current-state/CurrentStateReportMode";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type ReportMode = "current-state" | "audit";

function toMode(value: string | null): ReportMode {
  return value === "audit" ? "audit" : "current-state";
}

export default function ProjectReportPage() {
  const params = useParams();
  const projectId = params.id as string;
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const mode = toMode(searchParams.get("mode"));

  function selectMode(value: string) {
    const query = new URLSearchParams(searchParams.toString());
    if (toMode(value) === "audit") {
      query.set("mode", "audit");
    } else {
      query.delete("mode");
    }
    const search = query.toString();
    // Replace rather than push: switching modes should not add browser history entries.
    router.replace(search ? `${pathname}?${search}` : pathname, { scroll: false });
  }

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <Tabs value={mode} onValueChange={selectMode}>
        <TabsList className="print:hidden">
          <TabsTrigger value="current-state">Current state</TabsTrigger>
          <TabsTrigger value="audit">Audit export</TabsTrigger>
        </TabsList>
        <TabsContent value="current-state">
          <CurrentStateReportMode projectId={projectId} />
        </TabsContent>
        <TabsContent value="audit">
          <AuditReportMode projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
