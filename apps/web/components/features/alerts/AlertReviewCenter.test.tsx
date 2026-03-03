/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { AlertReviewCenter } from "@/components/features/alerts/AlertReviewCenter";

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

    fireEvent.click(screen.getByRole("button", { name: /approve a-1/i }));

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

    fireEvent.click(screen.getByRole("button", { name: /reject a-2/i }));

    const rejectButton = screen.getByRole("button", { name: /confirm reject/i });
    expect(rejectButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/rejection reason/i), {
      target: { value: "Insufficient evidence and false positive" },
    });

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

    fireEvent.click(screen.getByRole("button", { name: /edit a-3/i }));
    fireEvent.change(screen.getByLabelText(/title/i), {
      target: { value: "Updated warranty language mismatch" },
    });
    fireEvent.change(screen.getByLabelText(/severity/i), {
      target: { value: "high" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

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

    fireEvent.click(screen.getByRole("button", { name: /delete a-4/i }));

    expect(screen.getByRole("dialog", { name: /delete alert/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm delete/i })).toBeEnabled();
    expect(screen.getByRole("row", { name: /bid timeline conflict/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /confirm delete/i }));
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
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: /approve alert/i });
    expect(dialog).toHaveAttribute("aria-modal", "true");

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: /approve alert/i })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
