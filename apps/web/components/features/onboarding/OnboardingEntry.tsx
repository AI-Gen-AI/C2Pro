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
    <section aria-label="Onboarding entry">
      <h2>Get started fast</h2>
      <div role="status">
        {isFailed
          ? "Sample workspace setup failed"
          : "Ready to open a demo sample project workspace"}
      </div>
      <p className="text-sm text-muted-foreground">
        This path opens a non-production sample workspace for evaluation only.
        It does not provision a real customer project.
      </p>
      <ul aria-label="Onboarding checklist">
        <li>Open demo sample project workspace</li>
        <li>Review sample alerts</li>
        <li>Inspect sample stakeholders</li>
      </ul>

      <button
        type="button"
        onClick={onStartSampleProject}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onStartSampleProject();
          }
        }}
      >
        Open demo sample project
      </button>

      {isFailed ? (
        <>
          <div role="alert">
            {errorMessage ?? "Sample workspace setup failed"}
          </div>
          <button type="button">Retry demo setup</button>
        </>
      ) : null}
    </section>
  );
}

