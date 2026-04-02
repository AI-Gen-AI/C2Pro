/**
 * Test Suite ID: TASK-1467
 * Coverage: project shell header resolves project display names from the backend
 */
'use client';

import { ProjectTabs } from "@/components/layout/ProjectTabs";
import { useProject } from "@/hooks/useProject";

interface ProjectHeaderCardProps {
  projectId: string;
}

export function ProjectHeaderCard({ projectId }: ProjectHeaderCardProps) {
  const { data } = useProject(projectId);
  const projectName = data?.name?.trim() || projectId;

  return (
    <div className="rounded-md border bg-card p-4">
      <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
        Project
      </div>
      <h2 className="text-lg font-semibold">{projectName}</h2>
      <ProjectTabs projectId={projectId} />
    </div>
  );
}
