/**
 * Test Suite ID: TASK-1485
 * Route Coverage: nested project stakeholders route uses backend project context
 */
"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { StakeholderMatrix } from "@/components/stakeholders/StakeholderMatrix";
import { useProject } from "@/hooks/useProject";

export default function ProjectStakeholdersPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { data: project } = useProject(projectId);
  const projectName = project?.name?.trim() || projectId;

  useEffect(() => {
    if (!env.FEATURE_PHASE2_MODULES) {
      router.replace(`/projects/${projectId}`);
    }
  }, [router, projectId]);

  if (!env.FEATURE_PHASE2_MODULES) return null;

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
