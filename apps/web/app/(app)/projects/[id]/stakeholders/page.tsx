/**
 * Test Suite ID: TASK-1485
 * Route Coverage: nested project stakeholders route uses backend project context
 */
"use client";

import { useParams } from "next/navigation";
import { StakeholderMatrix } from "@/components/stakeholders/StakeholderMatrix";
import { useProject } from "@/hooks/useProject";

export default function ProjectStakeholdersPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { data: project } = useProject(projectId);
  const projectName = project?.name?.trim() || projectId;

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Stakeholders</h1>
        <p className="text-sm text-muted-foreground">
          Live stakeholder matrix for {projectName}.
        </p>
      </div>

      <StakeholderMatrix projectId={projectId} />
    </section>
  );
}
