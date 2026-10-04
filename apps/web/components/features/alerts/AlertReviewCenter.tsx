/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

type AlertSeverity = "critical" | "high" | "medium" | "low";
type AlertStatus = "pending" | "approved" | "rejected";

export interface ReviewAlert {
  id: string;
  title: string;
  severity: AlertSeverity;
  status: AlertStatus;
  clauseId?: string;
  addressableClauseId?: string;
  sourceDocumentId?: string;
  evidenceClaim?: string;
  evidenceQuote?: string;
  assignee?: string;
  rejectionReason?: string;
  resolutionNotes?: string;
  rootCause?: string;
}

type ModalState =
  | { kind: "none" }
  | { kind: "approve"; alertId: string }
  | { kind: "reject"; alertId: string }
  | { kind: "resolve"; alertId: string }
  | { kind: "edit"; alertId: string }
  | { kind: "delete"; alertId: string }
  | { kind: "create" };

interface AlertReviewCenterProps {
  projectId: string;
  alerts: ReviewAlert[];
  onApprove?: (alertId: string) => Promise<void>;
  onReject?: (alertId: string, reason: string) => Promise<void>;
  onResolve?: (
    alertId: string,
    resolution: string,
    rootCause?: string,
  ) => Promise<void>;
}

const SEVERITY_RANK: Record<AlertSeverity, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

type StatusFilter = "all" | AlertStatus;

function findAlert(items: ReviewAlert[], alertId: string): ReviewAlert | undefined {
  return items.find((item) => item.id === alertId);
}

export function AlertReviewCenter({
  projectId,
  alerts,
  onApprove,
  onReject,
  onResolve,
}: AlertReviewCenterProps) {
  const [items, setItems] = useState<ReviewAlert[]>(alerts);
  const [modal, setModal] = useState<ModalState>({ kind: "none" });
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [copiedAlertId, setCopiedAlertId] = useState<string | null>(null);
  const [approveConfirmed, setApproveConfirmed] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [rootCause, setRootCause] = useState("");
  const [editTitle, setEditTitle] = useState("");
  const [editSeverity, setEditSeverity] = useState<AlertSeverity>("medium");
  const [createTitle, setCreateTitle] = useState("");
  const [createSeverity, setCreateSeverity] = useState<AlertSeverity>("medium");
  const [createClauseId, setCreateClauseId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const persistedMode = Boolean(onApprove && onReject && onResolve);

  useEffect(() => {
    setItems(alerts);
  }, [alerts]);

  const activeAlert = useMemo(() => {
    if (modal.kind === "none" || modal.kind === "create") return undefined;
    return findAlert(items, modal.alertId);
  }, [items, modal]);

  const visibleItems = useMemo(
    () =>
      [...items]
        .filter((item) => statusFilter === "all" || item.status === statusFilter)
        .sort((left, right) => SEVERITY_RANK[right.severity] - SEVERITY_RANK[left.severity]),
    [items, statusFilter],
  );

  const closeModal = () => {
    setModal({ kind: "none" });
    setMutationError(null);
    setApproveConfirmed(false);
    setRejectReason("");
    setResolutionNotes("");
    setRootCause("");
    triggerRef.current?.focus();
  };

  const openApprove = (alertId: string, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setApproveConfirmed(false);
    setModal({ kind: "approve", alertId });
  };

  const openReject = (alertId: string, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setRejectReason("");
    setModal({ kind: "reject", alertId });
  };

  const openResolve = (alertId: string, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setResolutionNotes("");
    setRootCause("");
    setModal({ kind: "resolve", alertId });
  };

  const openEdit = (alertId: string, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    const current = findAlert(items, alertId);
    setEditTitle(current?.title ?? "");
    setEditSeverity(current?.severity ?? "medium");
    setModal({ kind: "edit", alertId });
  };

  const openDelete = (alertId: string, trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setModal({ kind: "delete", alertId });
  };

  const openCreate = (trigger: HTMLButtonElement) => {
    triggerRef.current = trigger;
    setCreateTitle("");
    setCreateSeverity("medium");
    setCreateClauseId("");
    setModal({ kind: "create" });
  };

  const saveApprove = async () => {
    if (modal.kind !== "approve" || !approveConfirmed) return;
    if (persistedMode && onApprove) {
      setIsSaving(true);
      setMutationError(null);
      try {
        await onApprove(modal.alertId);
        closeModal();
      } catch (error) {
        setMutationError(
          error instanceof Error ? error.message : "Could not approve alert.",
        );
      } finally {
        setIsSaving(false);
      }
      return;
    }
    setItems((prev) =>
      prev.map((item) =>
        item.id === modal.alertId ? { ...item, status: "approved", rejectionReason: undefined } : item,
      ),
    );
    closeModal();
  };

  const saveReject = async () => {
    if (modal.kind !== "reject" || rejectReason.trim().length === 0) return;
    if (persistedMode && onReject) {
      setIsSaving(true);
      setMutationError(null);
      try {
        await onReject(modal.alertId, rejectReason.trim());
        closeModal();
      } catch (error) {
        setMutationError(
          error instanceof Error ? error.message : "Could not reject alert.",
        );
      } finally {
        setIsSaving(false);
      }
      return;
    }
    setItems((prev) =>
      prev.map((item) =>
        item.id === modal.alertId
          ? { ...item, status: "rejected", rejectionReason: rejectReason.trim() }
          : item,
      ),
    );
    closeModal();
  };

  const requiresRootCause = (severity: AlertSeverity): boolean =>
    severity === "critical" || severity === "high";

  const saveResolve = async () => {
    if (modal.kind !== "resolve" || !activeAlert) return;
    if (resolutionNotes.trim().length === 0) return;
    if (requiresRootCause(activeAlert.severity) && rootCause.trim().length === 0) {
      return;
    }

    if (persistedMode && onResolve) {
      setIsSaving(true);
      setMutationError(null);
      try {
        await onResolve(
          modal.alertId,
          resolutionNotes.trim(),
          rootCause.trim() || undefined,
        );
        closeModal();
      } catch (error) {
        setMutationError(
          error instanceof Error ? error.message : "Could not resolve alert.",
        );
      } finally {
        setIsSaving(false);
      }
      return;
    }

    setItems((prev) =>
      prev.map((item) =>
        item.id === modal.alertId
          ? {
              ...item,
              status: "approved",
              resolutionNotes: resolutionNotes.trim(),
              rootCause: requiresRootCause(item.severity) ? rootCause : undefined,
              rejectionReason: undefined,
            }
          : item,
      ),
    );
    closeModal();
  };

  const saveEdit = () => {
    if (modal.kind !== "edit") return;
    setItems((prev) =>
      prev.map((item) =>
        item.id === modal.alertId
          ? { ...item, title: editTitle.trim() || item.title, severity: editSeverity }
          : item,
      ),
    );
    closeModal();
  };

  const saveDelete = () => {
    if (modal.kind !== "delete") return;
    setItems((prev) => prev.filter((item) => item.id !== modal.alertId));
    closeModal();
  };

  const saveCreate = () => {
    if (modal.kind !== "create" || createTitle.trim().length === 0) return;
    const nextId = `a-${items.length + 1}`;
    setItems((prev) => [
      ...prev,
      {
        id: nextId,
        title: createTitle.trim(),
        severity: createSeverity,
        status: "pending",
        clauseId: createClauseId.trim() || undefined,
        assignee: undefined,
      },
    ]);
    closeModal();
  };

  const buildProcurementMessage = (alert: ReviewAlert): string =>
    [
      `C2Pro coherence alert: ${alert.title}`,
      `Severity: ${alert.severity.toUpperCase()}`,
      `Status: ${alert.status}`,
      `Clause: ${alert.clauseId ?? "—"}`,
      `Evidence claim: ${alert.evidenceClaim ?? "—"}`,
      `Evidence quote: ${alert.evidenceQuote ?? "—"}`,
      `Owner: ${alert.assignee ?? "—"}`,
      "Please review the source evidence and confirm the vendor response or corrective action.",
    ].join("\n");

  const copyMessage = async (alert: ReviewAlert) => {
    setCopiedAlertId(alert.id);
    try {
      await navigator.clipboard?.writeText(buildProcurementMessage(alert));
    } catch {
      // Browser permission can be denied in QA/demo contexts; keep the UI action visible.
    }
  };

  return (
    <section aria-label="Alert Review Center" data-project-id={projectId}>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1>Alert Review Center</h1>
          <label className="mt-2 block text-sm" htmlFor="alert-status-filter">
            Status filter
          </label>
          <select
            id="alert-status-filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
        </div>
        {!persistedMode ? (
          <button
            type="button"
            onClick={(event) => openCreate(event.currentTarget)}
          >
            New Alert
          </button>
        ) : null}
      </div>

      <table aria-label="Alert Review Center">
        <thead>
          <tr>
            <th>Title</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Clause</th>
            <th>Evidence</th>
            <th>Assignee</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {visibleItems.map((alert) => (
            <tr key={alert.id}>
              <td>{alert.title}</td>
              <td>{alert.severity}</td>
              <td>{alert.status}</td>
              <td>
                {alert.clauseId ? (
                  alert.addressableClauseId && alert.sourceDocumentId ? (
                    <Link
                      href={
                        "/projects/" +
                        encodeURIComponent(projectId) +
                        "/evidence?documentId=" +
                        encodeURIComponent(alert.sourceDocumentId) +
                        "&highlightId=" +
                        encodeURIComponent(alert.addressableClauseId)
                      }
                      aria-label={"View evidence for " + alert.addressableClauseId}
                    >
                      {alert.clauseId}
                    </Link>
                  ) : (
                    alert.clauseId
                  )
                ) : (
                  "—"
                )}
              </td>
              <td>
                {alert.evidenceClaim || alert.evidenceQuote ? (
                  <div className="space-y-1">
                    {alert.evidenceClaim ? <div>{alert.evidenceClaim}</div> : null}
                    {alert.evidenceQuote ? (
                      <q className="text-sm text-muted-foreground">
                        {alert.evidenceQuote}
                      </q>
                    ) : null}
                  </div>
                ) : (
                  "—"
                )}
              </td>
              <td>{alert.assignee ?? "—"}</td>
              <td>
                <button
                  type="button"
                  onClick={(event) => openApprove(alert.id, event.currentTarget)}
                >
                  Approve {alert.id}
                </button>
                <button
                  type="button"
                  onClick={(event) => openReject(alert.id, event.currentTarget)}
                >
                  Reject {alert.id}
                </button>
                <button
                  type="button"
                  onClick={(event) => openResolve(alert.id, event.currentTarget)}
                >
                  Resolve {alert.id}
                </button>
                {!persistedMode ? (
                  <>
                    <button
                      type="button"
                      onClick={(event) => openEdit(alert.id, event.currentTarget)}
                    >
                      Edit {alert.id}
                    </button>
                    <button
                      type="button"
                      onClick={(event) => openDelete(alert.id, event.currentTarget)}
                    >
                      Delete {alert.id}
                    </button>
                  </>
                ) : null}
                <button
                  type="button"
                  onClick={() => {
                    copyMessage(alert).catch(() => {
                      // Clipboard failures are already handled by copyMessage.
                    });
                  }}
                >
                  Copy message {alert.id}
                </button>
                {copiedAlertId === alert.id ? <span>Copied</span> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {mutationError ? (
        <p role="alert" className="text-sm text-destructive">
          {mutationError}
        </p>
      ) : null}

      {modal.kind === "approve" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Approve Alert"
          onKeyDown={(event) => {
            if (event.key === "Escape") closeModal();
          }}
        >
          <p data-testid="alert-modal-context">{activeAlert?.title ?? "Unknown alert"}</p>
          <label>
            <input
              type="checkbox"
              checked={approveConfirmed}
              onChange={(event) => setApproveConfirmed(event.target.checked)}
            />
            I confirm approval
          </label>
          <button
            type="button"
            onClick={() => void saveApprove()}
            disabled={!approveConfirmed || isSaving}
          >
            Confirm Approve
          </button>
        </div>
      ) : null}

      {modal.kind === "reject" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Reject Alert"
          onKeyDown={(event) => {
            if (event.key === "Escape") closeModal();
          }}
        >
          <p data-testid="alert-modal-context">{activeAlert?.title ?? "Unknown alert"}</p>
          <label htmlFor="reject-reason">Rejection reason</label>
          <textarea
            id="reject-reason"
            value={rejectReason}
            onChange={(event) => setRejectReason(event.target.value)}
          />
          <button
            type="button"
            onClick={() => void saveReject()}
            disabled={rejectReason.trim().length === 0 || isSaving}
          >
            Confirm Reject
          </button>
        </div>
      ) : null}

      {modal.kind === "resolve" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Resolve Alert"
          onKeyDown={(event) => {
            if (event.key === "Escape") closeModal();
          }}
        >
          <p data-testid="alert-modal-context">{activeAlert?.title ?? "Unknown alert"}</p>
          <label htmlFor="resolution-notes">Resolution notes</label>
          <textarea
            id="resolution-notes"
            value={resolutionNotes}
            onChange={(event) => setResolutionNotes(event.target.value)}
          />
          {activeAlert && requiresRootCause(activeAlert.severity) ? (
            <>
              <label htmlFor="root-cause">Root cause</label>
              <select
                id="root-cause"
                value={rootCause}
                onChange={(event) => setRootCause(event.target.value)}
              >
                <option value="">Select root cause</option>
                <option value="schedule_delay">Schedule Delay</option>
                <option value="resource_constraint">Resource Constraint</option>
                <option value="scope_change">Scope Change</option>
                <option value="external_dependency">External Dependency</option>
                <option value="technical_issue">Technical Issue</option>
                <option value="budget_overrun">Budget Overrun</option>
                <option value="quality_issue">Quality Issue</option>
                <option value="other">Other</option>
              </select>
            </>
          ) : null}
          <button
            type="button"
            onClick={() => void saveResolve()}
            disabled={
              isSaving ||
              resolutionNotes.trim().length === 0 ||
              (activeAlert ? requiresRootCause(activeAlert.severity) && rootCause.trim().length === 0 : false)
            }
          >
            Confirm Resolve
          </button>
        </div>
      ) : null}

      {modal.kind === "edit" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Edit Alert"
          onKeyDown={(event) => {
            if (event.key === "Escape") closeModal();
          }}
        >
          <label htmlFor="edit-title">Title</label>
          <input
            id="edit-title"
            value={editTitle}
            onChange={(event) => setEditTitle(event.target.value)}
          />
          <label htmlFor="edit-severity">Severity</label>
          <select
            id="edit-severity"
            value={editSeverity}
            onChange={(event) => setEditSeverity(event.target.value as AlertSeverity)}
          >
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </select>
          <button type="button" onClick={saveEdit}>
            Save changes
          </button>
        </div>
      ) : null}

      {modal.kind === "delete" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Delete Alert"
          onKeyDown={(event) => {
            if (event.key === "Escape") closeModal();
          }}
        >
          <p>Delete alert permanently?</p>
          <button type="button" onClick={saveDelete}>
            Confirm delete
          </button>
        </div>
      ) : null}

      {modal.kind === "create" ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Create Alert"
          onKeyDown={(event) => {
            if (event.key === "Escape") closeModal();
          }}
        >
          <label htmlFor="create-title">Title</label>
          <input
            id="create-title"
            value={createTitle}
            onChange={(event) => setCreateTitle(event.target.value)}
          />
          <label htmlFor="create-severity">Severity</label>
          <select
            id="create-severity"
            value={createSeverity}
            onChange={(event) => setCreateSeverity(event.target.value as AlertSeverity)}
          >
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="medium">medium</option>
            <option value="low">low</option>
          </select>
          <label htmlFor="create-clause-id">Clause ID</label>
          <input
            id="create-clause-id"
            value={createClauseId}
            onChange={(event) => setCreateClauseId(event.target.value)}
          />
          <button type="button" onClick={saveCreate} disabled={createTitle.trim().length === 0}>
            Create alert
          </button>
        </div>
      ) : null}
    </section>
  );
}
