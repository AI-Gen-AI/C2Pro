/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
<<<<<<< HEAD
=======
import { act } from "react";
>>>>>>> 39961be9 (fix(tests): TASK-QA-077 + TASK-1480 — flake stabilization)
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { AlertReviewCenter } from "@/components/features/alerts/AlertReviewCenter";

vi.setConfig({ testTimeout: 10_000, hookTimeout: 10_000 });

function fireInAct(action: () => void) {
  act(() => {
    action();
  });
}

describe("S3-04 RED - AlertReviewCenter", () => {
  it("[S3-04-RED-UNIT-01] renders review table with required columns", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-1",
            title: "Delay penalty mismatch",
            severity: "high",
            status: "pending",
            clauseId: "c-101",
            assignee: "legal.reviewer",
          },
        ]}
      />,
    );

    expect(screen.getByRole("table", { name: /alert review center/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /severity/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /status/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /clause/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /assignee/i })).toBeInTheDocument();
  });

  it("[S3-04-RED-UNIT-02] opens approve modal with selected alert context", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-1",
            title: "Delay penalty mismatch",
            severity: "high",
            status: "pending",
            clauseId: "c-101",
            assignee: "legal.reviewer",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /approve a-1/i })));

    expect(screen.getByRole("dialog", { name: /approve alert/i })).toBeInTheDocument();
    expect(screen.getByTestId("alert-modal-context")).toHaveTextContent("Delay penalty mismatch");
    expect(screen.getByRole("button", { name: /confirm approve/i })).toBeDisabled();
  });

  it("[S3-04-RED-UNIT-03] reject modal requires reason before submit", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-2",
            title: "Insurance gap",
            severity: "critical",
            status: "pending",
            clauseId: "c-202",
            assignee: "risk.owner",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /reject a-2/i })));

    const rejectButton = screen.getByRole("button", { name: /confirm reject/i });
    expect(rejectButton).toBeDisabled();

    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/rejection reason/i), {
        target: { value: "Insufficient evidence and false positive" },
      }),
    );

    expect(rejectButton).toBeEnabled();
  });

  it("[S3-04-RED-UNIT-04] supports edit flow and updates row fields", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-3",
            title: "Outdated warranty text",
            severity: "medium",
            status: "pending",
            clauseId: "c-303",
            assignee: "qa.owner",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /edit a-3/i })));
    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/title/i), {
        target: { value: "Updated warranty language mismatch" },
      }),
    );
    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/severity/i), {
        target: { value: "high" },
      }),
    );
    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /save changes/i })));

    expect(screen.getByRole("row", { name: /updated warranty language mismatch/i })).toHaveTextContent(
      /high/i,
    );
  });

  it("[S3-04-RED-UNIT-05] requires delete confirmation before row removal", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-4",
            title: "Bid timeline conflict",
            severity: "low",
            status: "pending",
            clauseId: "c-404",
            assignee: "planner.owner",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /delete a-4/i })));

    expect(screen.getByRole("dialog", { name: /delete alert/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm delete/i })).toBeEnabled();
    expect(screen.getByRole("row", { name: /bid timeline conflict/i })).toBeInTheDocument();

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /confirm delete/i })));
    expect(screen.queryByRole("row", { name: /bid timeline conflict/i })).not.toBeInTheDocument();
  });

  it("[S3-04-RED-UNIT-06] modal has dialog semantics, ESC close, and focus return", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-5",
            title: "Retention clause ambiguity",
            severity: "high",
            status: "pending",
            clauseId: "c-505",
            assignee: "legal.owner",
          },
        ]}
      />,
    );

    const trigger = screen.getByRole("button", { name: /approve a-5/i });
    trigger.focus();
    fireInAct(() => fireEvent.click(trigger));

    const dialog = screen.getByRole("dialog", { name: /approve alert/i });
    expect(dialog).toHaveAttribute("aria-modal", "true");

    fireInAct(() => fireEvent.keyDown(dialog, { key: "Escape" }));
    expect(screen.queryByRole("dialog", { name: /approve alert/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("[S3-04-RED-UNIT-07] resolve modal requires root cause for critical alerts before confirm", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-6",
            title: "Missing liquidated damages fallback",
            severity: "critical",
            status: "pending",
            clauseId: "c-606",
            assignee: "risk.owner",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /resolve a-6/i })));

    const resolveButton = screen.getByRole("button", { name: /confirm resolve/i });
    expect(screen.getByLabelText(/root cause/i)).toBeInTheDocument();
    expect(resolveButton).toBeDisabled();

    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/resolution notes/i), {
        target: { value: "Contract amendment issued and workflow updated." },
      }),
    );
    expect(resolveButton).toBeDisabled();

    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/root cause/i), {
        target: { value: "scope_change" },
      }),
    );
    expect(resolveButton).toBeEnabled();
  });

  it("[S3-04-RED-UNIT-08] resolve modal omits root cause requirement for medium severity alerts", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-7",
            title: "Clarify payment milestone wording",
            severity: "medium",
            status: "pending",
            clauseId: "c-707",
            assignee: "finance.analyst",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /resolve a-7/i })));

    expect(screen.queryByLabelText(/root cause/i)).not.toBeInTheDocument();
    const resolveButton = screen.getByRole("button", { name: /confirm resolve/i });
    expect(resolveButton).toBeDisabled();

    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/resolution notes/i), {
        target: { value: "Reviewed with owner and marked resolved." },
      }),
    );

    expect(resolveButton).toBeEnabled();
  });

  it("[TS-UD-COH-V1-09] sorts alerts by severity and filters by status", () => {
    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-low",
            title: "Low notice wording",
            severity: "low",
            status: "pending",
            clauseId: "c-low",
            assignee: "project.manager",
          },
          {
            id: "a-critical",
            title: "Critical LD cap conflict",
            severity: "critical",
            status: "approved",
            clauseId: "c-critical",
            assignee: "legal.owner",
          },
          {
            id: "a-high",
            title: "High budget exposure",
            severity: "high",
            status: "pending",
            clauseId: "c-high",
            assignee: "finance.analyst",
          },
        ]}
      />,
    );

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((row) => row.textContent)).toEqual([
      expect.stringContaining("Critical LD cap conflict"),
      expect.stringContaining("High budget exposure"),
      expect.stringContaining("Low notice wording"),
    ]);

    fireInAct(() =>
      fireEvent.change(screen.getByLabelText(/status filter/i), {
        target: { value: "pending" },
      }),
    );

    expect(screen.queryByText(/critical ld cap conflict/i)).not.toBeInTheDocument();
    expect(screen.getByText(/high budget exposure/i)).toBeInTheDocument();
    expect(screen.getByText(/low notice wording/i)).toBeInTheDocument();
  });

  it("[TS-UD-COH-V1-09] copies a procurement-ready alert message", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(
      <AlertReviewCenter
        projectId="proj_demo_001"
        alerts={[
          {
            id: "a-copy",
            title: "AUDIT_INCOMPLETE: missing schedule and budget",
            severity: "medium",
            status: "pending",
            clauseId: "audit-meta",
            assignee: "project.manager",
          },
        ]}
      />,
    );

    fireInAct(() => fireEvent.click(screen.getByRole("button", { name: /copy message a-copy/i })));

    expect(writeText).toHaveBeenCalledWith(
      expect.stringContaining("AUDIT_INCOMPLETE: missing schedule and budget"),
    );
    expect(await screen.findByText(/copied/i)).toBeInTheDocument();
  });
});
