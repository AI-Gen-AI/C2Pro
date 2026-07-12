/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */
"use client";

interface OnboardingEntryProps {
  onStartSampleProject: () => void;
  initialState?: "idle" | "failed";
  errorMessage?: string;
}

export function OnboardingEntry({
  onStartSampleProject,
  initialState = "idle",
  errorMessage,
}: OnboardingEntryProps) {
  const isFailed = initialState === "failed";

  return (
    <section aria-label="Onboarding entry" className="space-y-4">
      <h2 className="text-xl font-semibold">Get started fast</h2>
      <div role="status" className="text-sm text-muted-foreground">
        {isFailed
          ? "Sample workspace setup failed"
          : "Ready to open a demo sample project workspace"}
      </div>
      <p className="text-sm text-muted-foreground">
        This path opens a non-production sample workspace for evaluation only.
        It does not provision a real customer project.
      </p>
      <ul aria-label="Onboarding checklist" className="list-disc list-inside text-sm text-muted-foreground text-left max-w-sm mx-auto space-y-1">
        <li>Open demo sample project workspace</li>
        <li>Review sample alerts</li>
        <li>Inspect sample stakeholders</li>
      </ul>

      <button
        type="button"
        className="inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground font-medium text-sm h-10 px-4 py-2 hover:bg-primary/90 transition-colors"
        onClick={onStartSampleProject}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onStartSampleProject();
          }
        }}
      >
        Start with sample project
      </button>

      {isFailed ? (
        <div className="mt-4 space-y-2">
          <div role="alert" className="text-sm font-semibold text-destructive">
            {errorMessage ?? "Sample workspace setup failed"}
          </div>
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-md border border-input bg-background font-medium text-sm h-10 px-4 py-2 hover:bg-accent hover:text-accent-foreground transition-colors"
            onClick={onStartSampleProject}
          >
            Retry setup
          </button>
        </div>
      ) : null}
    </section>
  );
}
