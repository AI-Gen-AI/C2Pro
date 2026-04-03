/**
 * Test Suite ID: TASK-1486
 * Route Coverage: nested project settings route uses backend project update flow
 */
"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useProject } from "@/hooks/useProject";
import { useUpdateProject } from "@/hooks/useUpdateProject";

type ProjectSettingsDraft = {
  name: string;
  code: string;
  description: string;
  project_type: string;
  status: string;
  estimated_budget: string;
  currency: string;
};

const EMPTY_DRAFT: ProjectSettingsDraft = {
  name: "",
  code: "",
  description: "",
  project_type: "",
  status: "",
  estimated_budget: "",
  currency: "",
};

export default function ProjectSettingsPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { data: project } = useProject(projectId);
  const { mutateAsync: updateProject, isPending, error } = useUpdateProject();
  const [draft, setDraft] = useState<ProjectSettingsDraft>(EMPTY_DRAFT);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!project) {
      return;
    }

    setDraft({
      name: project.name ?? "",
      code: project.code ?? "",
      description: project.description ?? "",
      project_type: project.project_type ?? "",
      status: project.status ?? "",
      estimated_budget:
        typeof project.estimated_budget === "number"
          ? String(project.estimated_budget)
          : "",
      currency: project.currency ?? "",
    });
  }, [project]);

  const projectName = project?.name?.trim() || projectId;

  async function handleSave() {
    setSaveMessage(null);

    await updateProject({
      projectId,
      data: {
        name: draft.name.trim(),
        code: draft.code.trim() || null,
        description: draft.description.trim() || null,
        project_type: draft.project_type || null,
        status: draft.status || null,
        estimated_budget: draft.estimated_budget.trim()
          ? Number(draft.estimated_budget)
          : null,
        currency: draft.currency.trim() || null,
      },
    });

    setSaveMessage("Settings saved.");
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Project Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure {projectName} using the live backend project record.
        </p>
      </div>

      <div className="rounded-2xl border border-border/80 bg-card/85 p-6 shadow-sm">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="project-name">Project Name</Label>
            <Input
              id="project-name"
              value={draft.name}
              onChange={(event) =>
                setDraft((current) => ({ ...current, name: event.target.value }))
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="project-code">Project Code</Label>
            <Input
              id="project-code"
              value={draft.code}
              onChange={(event) =>
                setDraft((current) => ({ ...current, code: event.target.value }))
              }
            />
          </div>
          <div className="grid gap-2 md:col-span-2">
            <Label htmlFor="project-description">Description</Label>
            <Textarea
              id="project-description"
              value={draft.description}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  description: event.target.value,
                }))
              }
              rows={4}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="project-type">Project Type</Label>
            <Input
              id="project-type"
              value={draft.project_type}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  project_type: event.target.value,
                }))
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="project-status">Status</Label>
            <Input
              id="project-status"
              value={draft.status}
              onChange={(event) =>
                setDraft((current) => ({ ...current, status: event.target.value }))
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="estimated-budget">Estimated Budget</Label>
            <Input
              id="estimated-budget"
              inputMode="numeric"
              value={draft.estimated_budget}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  estimated_budget: event.target.value,
                }))
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="project-currency">Currency</Label>
            <Input
              id="project-currency"
              value={draft.currency}
              onChange={(event) =>
                setDraft((current) => ({
                  ...current,
                  currency: event.target.value,
                }))
              }
            />
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button
            type="button"
            className="rounded-xl shadow-sm"
            disabled={isPending}
            onClick={() => void handleSave()}
          >
            Save Project Settings
          </Button>
          {saveMessage ? (
            <p className="text-sm text-muted-foreground">{saveMessage}</p>
          ) : null}
          {error ? (
            <p className="text-sm text-destructive">
              {error instanceof Error ? error.message : "Project update failed."}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
