'use client';

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useCreateProjectApiV1ProjectsPost } from "@/lib/api/generated/projects/projects";

const PROJECT_TYPE_OPTIONS = [
  { value: "epc", label: "EPC" },
  { value: "civil", label: "Civil" },
  { value: "building", label: "Building" },
  { value: "maritime", label: "Maritime" },
  { value: "chemical", label: "Chemical" },
  { value: "energy", label: "Energy" },
  { value: "municipal", label: "Municipal" },
  { value: "oil_gas", label: "Oil & Gas" },
  { value: "mining", label: "Mining" },
];

type CreateProjectStep = 0 | 1 | 2;

interface CreateProjectDraft {
  name: string;
  code: string;
  projectType: string;
  clientName: string;
  description: string;
  currency: string;
}

interface CreateProjectWizardProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateProjectWizard({ open, onOpenChange }: CreateProjectWizardProps) {
  const router = useRouter();
  const createProject = useCreateProjectApiV1ProjectsPost();

  const [createProjectStep, setCreateProjectStep] = useState<CreateProjectStep>(0);
  const [createProjectError, setCreateProjectError] = useState<string | null>(null);
  const [createProjectDraft, setCreateProjectDraft] = useState<CreateProjectDraft>({
    name: "",
    code: "",
    projectType: "",
    clientName: "",
    description: "",
    currency: "EUR",
  });

  const updateCreateProjectDraft = (field: keyof CreateProjectDraft, value: string) => {
    setCreateProjectDraft((currentDraft) => ({
      ...currentDraft,
      [field]: value,
    }));
  };

  const canAdvanceCreateProjectStep = createProjectDraft.name.trim().length > 0;

  const submitCreateProjectWizard = async () => {
    const trimmedName = createProjectDraft.name.trim();
    if (!trimmedName) {
      setCreateProjectError("Project name is required.");
      return;
    }

    try {
      setCreateProjectError(null);
      const project = await createProject.mutateAsync({
        data: {
          name: trimmedName,
          code: createProjectDraft.code.trim() || undefined,
          description: createProjectDraft.description.trim() || undefined,
          client_name: createProjectDraft.clientName.trim() || undefined,
          currency: createProjectDraft.currency,
          project_type: createProjectDraft.projectType || undefined,
        },
      });

      onOpenChange(false);
      setCreateProjectStep(0);
      router.push(`/projects/${project.id}/documents`);
    } catch (mutationError: unknown) {
      const message =
        mutationError instanceof Error
          ? mutationError.message
          : "An unexpected error occurred during project creation. Please try again.";
      setCreateProjectError(message);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        onOpenChange(isOpen);
        if (!isOpen) {
          setCreateProjectStep(0);
          setCreateProjectError(null);
        }
      }}
    >
      <DialogContent
        aria-describedby="create-project-description"
        className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-2xl sm:rounded-2xl"
      >
        <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
          <DialogTitle>Create project</DialogTitle>
          <DialogDescription id="create-project-description">
            Step {createProjectStep + 1} of 3. Capture the project essentials, then review before creating it.
          </DialogDescription>
        </DialogHeader>

        {createProjectStep === 0 ? (
          <div className="grid gap-4 rounded-2xl border bg-background/90 p-4 shadow-sm">
            <label className="grid gap-2 text-sm text-foreground">
              <span>Project Name *</span>
              <Input
                aria-label="Project name"
                data-testid="project-name-input"
                value={createProjectDraft.name}
                onChange={(event) =>
                  updateCreateProjectDraft("name", event.target.value)
                }
                className="rounded-xl border-border/80 bg-background/95"
              />
            </label>
            <label className="grid gap-2 text-sm text-foreground">
              <span>Project Code</span>
              <Input
                aria-label="Project code"
                data-testid="project-code-input"
                value={createProjectDraft.code}
                onChange={(event) =>
                  updateCreateProjectDraft("code", event.target.value)
                }
                className="rounded-xl border-border/80 bg-background/95"
              />
            </label>
            <label className="grid gap-2 text-sm text-foreground">
              <span>Project Type</span>
              <select
                aria-label="Project type"
                data-testid="project-type-select"
                className="h-10 rounded-xl border border-border/80 bg-background/95 px-3 py-2 text-sm"
                value={createProjectDraft.projectType}
                onChange={(event) =>
                  updateCreateProjectDraft("projectType", event.target.value)
                }
              >
                <option value="">Select project type</option>
                {PROJECT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        ) : null}

        {createProjectStep === 1 ? (
          <div className="grid gap-4 rounded-2xl border bg-background/90 p-4 shadow-sm">
            <label className="grid gap-2 text-sm text-foreground">
              <span>Client Name</span>
              <Input
                aria-label="Client name"
                data-testid="client-name-input"
                value={createProjectDraft.clientName}
                onChange={(event) =>
                  updateCreateProjectDraft("clientName", event.target.value)
                }
                className="rounded-xl border-border/80 bg-background/95"
              />
            </label>
            <label className="grid gap-2 text-sm text-foreground">
              <span>Project Description</span>
              <textarea
                aria-label="Project description"
                data-testid="project-description-input"
                className="min-h-28 rounded-xl border border-border/80 bg-background/95 px-3 py-2 text-sm"
                value={createProjectDraft.description}
                onChange={(event) =>
                  updateCreateProjectDraft("description", event.target.value)
                }
              />
            </label>
            <label className="grid gap-2 text-sm text-foreground">
              <span>Currency</span>
              <select
                aria-label="Currency"
                data-testid="currency-select"
                className="h-10 rounded-xl border border-border/80 bg-background/95 px-3 py-2 text-sm"
                value={createProjectDraft.currency}
                onChange={(event) =>
                  updateCreateProjectDraft("currency", event.target.value)
                }
              >
                <option value="EUR">EUR</option>
                <option value="USD">USD</option>
                <option value="GBP">GBP</option>
              </select>
            </label>
          </div>
        ) : null}

        {createProjectStep === 2 ? (
          <div className="grid gap-4 rounded-2xl border bg-muted/25 p-4 shadow-sm">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Project name
              </div>
              <div className="mt-1 text-sm font-medium" data-testid="review-name">
                {createProjectDraft.name || "Not provided"}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Project code
              </div>
              <div className="mt-1 text-sm font-medium" data-testid="review-code">
                {createProjectDraft.code || "Not provided"}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Project type
              </div>
              <div className="mt-1 text-sm font-medium uppercase" data-testid="review-type">
                {createProjectDraft.projectType || "Not provided"}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Client name
              </div>
              <div className="mt-1 text-sm font-medium" data-testid="review-client">
                {createProjectDraft.clientName || "Not provided"}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Description
              </div>
              <div className="mt-1 text-sm font-medium" data-testid="review-description">
                {createProjectDraft.description || "Not provided"}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Currency
              </div>
              <div className="mt-1 text-sm font-medium" data-testid="review-currency">
                {createProjectDraft.currency}
              </div>
            </div>
          </div>
        ) : null}

        {createProjectError ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive shadow-sm">
            {createProjectError}
          </div>
        ) : null}

        <DialogFooter className="flex flex-wrap gap-2 rounded-2xl border bg-background/80 px-4 py-4">
          <Button
            type="button"
            variant="outline"
            className="rounded-xl"
            onClick={() =>
              createProjectStep === 0
                ? onOpenChange(false)
                : setCreateProjectStep((currentStep) =>
                    Math.max(0, currentStep - 1) as CreateProjectStep,
                  )
            }
          >
            {createProjectStep === 0 ? "Cancel" : "Previous step"}
          </Button>
          {createProjectStep < 2 ? (
            <Button
              type="button"
              className="rounded-xl"
              onClick={() =>
                setCreateProjectStep((currentStep) =>
                  Math.min(2, currentStep + 1) as CreateProjectStep,
                )
              }
              disabled={createProjectStep === 0 && !canAdvanceCreateProjectStep}
            >
              {createProjectStep === 1 ? "Review project" : "Next step"}
            </Button>
          ) : (
            <Button
              type="button"
              className="rounded-xl"
              data-testid="create-project-button"
              onClick={submitCreateProjectWizard}
              disabled={createProject.isPending}
            >
              {createProject.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create project"
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
