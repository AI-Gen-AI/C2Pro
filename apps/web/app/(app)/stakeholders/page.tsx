"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { env } from "@/config/env";
import { useProjects } from "@/hooks/useProjects";
import type { ProjectListItem } from "@/lib/api/contracts";
import { StakeholderMatrix } from "@/components/stakeholders/StakeholderMatrix";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function StakeholdersPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialProjectId = searchParams.get("projectId") ?? "all";
  const [projectId, setProjectId] = useState(initialProjectId);
  const { data: projects } = useProjects(true);

  useEffect(() => {
    if (!env.FEATURE_PHASE2_MODULES) {
      router.replace("/dashboard");
    }
  }, [router]);

  useEffect(() => {
    setProjectId(initialProjectId);
  }, [initialProjectId]);

  if (!env.FEATURE_PHASE2_MODULES) return null;

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Stakeholders</h1>
        <p className="text-sm text-muted-foreground">
          Select a project to load its live stakeholder matrix from the backend.
        </p>
      </div>

      <div className="max-w-sm">
        <Select value={projectId} onValueChange={setProjectId}>
          <SelectTrigger>
            <SelectValue placeholder="Select a project" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Select a project</SelectItem>
            {(projects ?? []).map((project: ProjectListItem) => (
              <SelectItem key={project.id} value={project.id}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <StakeholderMatrix projectId={projectId === "all" ? undefined : projectId} />

      {projectId === "all" ? (
        <p className="text-sm text-muted-foreground">
          Choose a project to load stakeholders and enable live matrix updates.
        </p>
      ) : null}
    </section>
  );
}
