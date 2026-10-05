/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
import { act } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
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
            assignee: "legal.owner",
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

  it("[TASK-FRT-178] renders honest placeholders when backend alerts have no clause or assignee", () => {
    render(
      <AlertReviewCenter
        projectId="proj_real_001"
        alerts={[
          {
            id: "alert-real",
            title: "Backend alert without reviewer metadata",
            severity: "medium",
            status: "pending",
          },
        ]}
      />,
    );

    const row = screen.getByRole("row", {
      name: /backend alert without reviewer metadata/i,
    });
    expect(row).toHaveTextContent("—");
    expect(row).not.toHaveTextContent(/legal\.reviewer|finance\.analyst|clause-/i);
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
            assignee: "legal.owner",
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
            assignee: "cost.owner",
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
            assignee: "cost.owner",
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


  it("[B1-PERSIST-01] delegates canonical mutations and hides demo-only destructive controls", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    const onReject = vi.fn().mockResolvedValue(undefined);
    const onResolve = vi.fn().mockResolvedValue(undefined);

    render(
      <AlertReviewCenter
        projectId="proj-real-001"
        alerts={[
          {
            id: "alert-persist",
            title: "Schedule mismatch",
            severity: "high",
            status: "pending",
          },
        ]}
        onApprove={onApprove}
        onReject={onReject}
        onResolve={onResolve}
      />,
    );

    expect(screen.queryByRole("button", { name: /new alert/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit alert-persist/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete alert-persist/i })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /approve alert-persist/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /i confirm approval/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm approve/i }));

    await waitFor(() => expect(onApprove).toHaveBeenCalledWith("alert-persist"));
  });

  it("[B1-PERSIST-02] sends rejection reason and resolution payload to canonical handlers", async () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    const onReject = vi.fn().mockResolvedValue(undefined);
    const onResolve = vi.fn().mockResolvedValue(undefined);

    render(
      <AlertReviewCenter
        projectId="proj-real-001"
        alerts={[
          {
            id: "alert-review",
            title: "Insurance conflict",
            severity: "high",
            status: "pending",
          },
        ]}
        onApprove={onApprove}
        onReject={onReject}
        onResolve={onResolve}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /reject alert-review/i }));
    fireEvent.change(screen.getByLabelText(/rejection reason/i), {
      target: { value: "False positive after source review" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirm reject/i }));
    await waitFor(() =>
      expect(onReject).toHaveBeenCalledWith(
        "alert-review",
        "False positive after source review",
      ),
    );

    fireEvent.click(screen.getByRole("button", { name: /resolve alert-review/i }));
    fireEvent.change(screen.getByLabelText(/resolution notes/i), {
      target: { value: "Contract wording corrected and source evidence updated." },
    });
    fireEvent.change(screen.getByLabelText(/root cause/i), {
      target: { value: "scope_change" },
    });
    fireEvent.click(screen.getByRole("button", { name: /confirm resolve/i }));
    await waitFor(() =>
      expect(onResolve).toHaveBeenCalledWith(
        "alert-review",
        "Contract wording corrected and source evidence updated.",
        "scope_change",
      ),
    );
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

describe("Line B evidence provenance", () => {
  it("deep-links only a database-verified clause/document pair", () => {
    render(
      <AlertReviewCenter
        projectId="proj-42"
        alerts={[
          {
            id: "a-evidence",
            title: "Schedule gap",
            severity: "medium",
            status: "pending",
            clauseId: "11111111-1111-4111-8111-111111111111",
            addressableClauseId: "11111111-1111-4111-8111-111111111111",
            sourceDocumentId: "22222222-2222-4222-8222-222222222222",
            evidenceClaim: "Milestone gap detected",
            evidenceQuote: "Milestone B starts thirty days later",
          },
        ]}
      />,
    );

    expect(screen.getByText("Milestone gap detected")).toBeInTheDocument();
    expect(screen.getByText(/Milestone B starts thirty days later/)).toBeInTheDocument();
    const link = screen.getByRole("link", {
      name: /view evidence for 11111111-1111-4111-8111-111111111111/i,
    });
    expect(link).toHaveAttribute(
      "href",
      "/projects/proj-42/evidence?documentId=22222222-2222-4222-8222-222222222222&highlightId=11111111-1111-4111-8111-111111111111",
    );
  });

  it("shows an external detector locator without fabricating a deep-link", () => {
    render(
      <AlertReviewCenter
        projectId="proj-42"
        alerts={[
          {
            id: "a-unresolved",
            title: "Fallback finding",
            severity: "low",
            status: "pending",
            clauseId: "parsed_deadbeef",
            sourceDocumentId: "22222222-2222-4222-8222-222222222222",
            evidenceClaim: "Parsed evidence only",
          },
        ]}
      />,
    );

    expect(screen.getByText("parsed_deadbeef")).toBeInTheDocument();
    expect(screen.getByText("Parsed evidence only")).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /view evidence/i }),
    ).not.toBeInTheDocument();
  });
});

