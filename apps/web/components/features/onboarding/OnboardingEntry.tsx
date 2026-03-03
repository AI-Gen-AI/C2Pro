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
      <div role="status">{isFailed ? "Provisioning failed" : "Ready to bootstrap sample project"}</div>
      <ul aria-label="Onboarding checklist">
        <li>Bootstrap sample project</li>
        <li>Review alerts</li>
        <li>Inspect stakeholders</li>
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
        Start with sample project
      </button>

      {isFailed ? (
        <>
          <div role="alert">{errorMessage ?? "Provisioning failed"}</div>
          <button type="button">Retry setup</button>
        </>
      ) : null}
    </section>
  );
}

