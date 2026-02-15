/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { OnboardingEntry } from "@/src/components/features/onboarding/OnboardingEntry";

describe("S3-11 RED - OnboardingEntry", () => {
  it("[S3-11-RED-UNIT-01] renders sample project CTA and checklist", () => {
    render(<OnboardingEntry onStartSampleProject={() => {}} />);

    expect(screen.getByRole("button", { name: /start with sample project/i })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /onboarding checklist/i })).toBeInTheDocument();
  });

  it("[S3-11-RED-UNIT-03] shows actionable timeout error with retry", () => {
    render(
      <OnboardingEntry
        onStartSampleProject={() => {}}
        initialState="failed"
        errorMessage="Provisioning timed out"
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/provisioning timed out/i);
    expect(screen.getByRole("button", { name: /retry setup/i })).toBeInTheDocument();
  });

  it("[S3-11-RED-UNIT-05] exposes accessible headings/list/live status and keyboard activation", () => {
    const onStart = vi.fn();
    render(<OnboardingEntry onStartSampleProject={onStart} />);

    expect(screen.getByRole("heading", { name: /get started fast/i })).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();

    const cta = screen.getByRole("button", { name: /start with sample project/i });
    cta.focus();
    fireEvent.keyDown(cta, { key: "Enter" });
    expect(onStart).toHaveBeenCalled();
  });
});
