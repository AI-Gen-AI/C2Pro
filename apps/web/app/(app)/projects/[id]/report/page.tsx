/**
 * Test Suite ID: TS-P0D-REPORT-UI-003
 * Project Report route: current state report (default) and the audit export.
 */
"use client";

import { useParams } from "next/navigation";
import { AuditReportMode } from "@/components/features/report/AuditReportMode";
import { CurrentStateReportMode } from "@/components/features/report/current-state/CurrentStateReportMode";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ProjectReportPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <Tabs defaultValue="current-state">
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
