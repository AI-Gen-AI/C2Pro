/**
 * Test Suite ID: TS-P0D-REPORT-UI-001
 * Current State Report view.
 *
 * Every section states whether data is available, how fresh it is, and how
 * well it traces back to source evidence. Unknown values are named as
 * unknown; they are never rendered as zero.
 */
"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { CurrentStateReport } from "@/lib/api/generated/models";
import {
  LEVEL_CLASSES,
  LEVEL_LABELS,
  STATUS_CLASSES,
  STATUS_LABELS,
  TIER_CLASSES,
  TIER_LABELS,
  UNKNOWN_LABEL,
  documentStatusLabel,
  formatDate,
  formatDateTime,
  formatMoney,
  formatScore,
  humanize,
  sectionLabel,
  tierLabel,
} from "./current-state-format";

type Sections = CurrentStateReport["sections"];

type SectionEnvelope = Pick<
  Sections["documents"],
  "status" | "status_reason" | "source_domain" | "source_as_of" | "source_ref" | "evidence_tier" | "evidence_note"
>;

const CONTENT_SECTION_ORDER = [
  "documents",
  "health",
  "missing_evidence",
  "coherence",
  "alerts",
  "hitl",
  "budget",
  "wbs",
  "stakeholders",
  "raci",
  "risks",
  "obligations",
  "schedule",
] as const;

type ContentSectionKey = (typeof CONTENT_SECTION_ORDER)[number];

const HEADING_CLASS = "text-base font-semibold leading-none tracking-tight";

export function CurrentStateReportView({ report }: { report: CurrentStateReport }) {
  const { sections } = report;

  return (
    <div className="space-y-6">
      <header data-testid="report-header" className="border-b pb-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Current state · Generated {formatDateTime(report.generated_at)}
        </p>
        <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-2xl font-semibold leading-tight">{report.project.name}</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {report.project.code ? `${report.project.code} · ` : ""}
              Report fingerprint {report.content_fingerprint.slice(0, 12)} (same fingerprint means the same state)
            </p>
          </div>
          {report.project.status ? <Badge variant="outline">{humanize(report.project.status)}</Badge> : null}
        </div>
      </header>

      <ExecutiveSummary sections={sections} />

      <div className="grid gap-4 lg:grid-cols-2">
        {CONTENT_SECTION_ORDER.map((key) => {
          const envelope: SectionEnvelope = sections[key];
          return (
            <SectionCard key={key} sectionKey={key} section={envelope}>
              <SectionBody sectionKey={key} sections={sections} />
            </SectionCard>
          );
        })}
      </div>

      <EvidenceQuality sections={sections} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------

function ExecutiveSummary({ sections }: { sections: Sections }) {
  const summary = sections.executive_summary.data;
  if (!summary) {
    return null;
  }
  const notCovered = [
    { label: "Not modeled yet", keys: summary.not_modeled_section_keys },
    { label: "Unavailable", keys: summary.unavailable_section_keys },
    { label: "Could not load", keys: summary.error_section_keys },
  ].filter((group) => group.keys.length > 0);

  const documentCount = summary.document_count;
  const parsedCount = summary.parsed_document_count;
  let documentsFact: string;
  if (documentCount === null || documentCount === undefined) {
    documentsFact = "Unknown";
  } else if (parsedCount === null || parsedCount === undefined) {
    documentsFact = `${documentCount} uploaded (processing status partially loaded)`;
  } else {
    documentsFact = `${documentCount} uploaded · ${parsedCount} processed`;
  }

  return (
    <Card data-testid="executive-summary">
      <CardHeader>
        <h3 className={HEADING_CLASS}>What needs attention</h3>
      </CardHeader>
      <CardContent className="space-y-4">
        {summary.attention_items.length > 0 ? (
          <ul className="space-y-2">
            {summary.attention_items.map((entry) => (
              <li
                key={`${entry.kind}-${entry.section_key}`}
                data-testid="attention-item"
                className="flex flex-wrap items-center gap-2 text-sm"
              >
                <Badge variant="outline" className={cn(LEVEL_CLASSES[entry.level])}>
                  {LEVEL_LABELS[entry.level] ?? entry.level}
                </Badge>
                <span>{entry.message}</span>
                <span className="text-xs text-muted-foreground">{sectionLabel(entry.section_key)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing requires attention in the data that is available.</p>
        )}

        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <Fact label="Documents">{documentsFact}</Fact>
          <Fact label="Health composite">
            {summary.health_composite_score === null || summary.health_composite_score === undefined
              ? UNKNOWN_LABEL
              : `${formatScore(summary.health_composite_score)} (${humanize(summary.health_composite_band ?? "unknown")})`}
          </Fact>
        </dl>

        {notCovered.length > 0 ? (
          <div className="space-y-1 rounded-md bg-muted/40 p-3 text-sm">
            <p className="font-medium">This report does not cover everything</p>
            {notCovered.map((group) => (
              <p key={group.label} className="text-muted-foreground">
                {group.label}: {group.keys.map(sectionLabel).join(", ")}
              </p>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section shell
// ---------------------------------------------------------------------------

const SNAPSHOT_REF_PREFIX = "project_snapshot:";

function sourceLine(section: SectionEnvelope): string {
  const asOf = section.source_as_of
    ? `As of ${formatDateTime(section.source_as_of)}`
    : "Source records carry no timestamp";
  const ref = section.source_ref;
  if (ref && ref.startsWith(SNAPSHOT_REF_PREFIX)) {
    return `${asOf} · snapshot ${ref.slice(SNAPSHOT_REF_PREFIX.length, SNAPSHOT_REF_PREFIX.length + 8)}`;
  }
  return asOf;
}

function SectionCard({
  sectionKey,
  section,
  children,
}: {
  sectionKey: ContentSectionKey;
  section: SectionEnvelope;
  children: ReactNode;
}) {
  const available = section.status === "available";
  const headingId = `section-${sectionKey}-heading`;
  return (
    <Card data-testid={`section-${sectionKey}`} aria-labelledby={headingId} className="print:break-inside-avoid">
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 id={headingId} className={HEADING_CLASS}>
            {sectionLabel(sectionKey)}
          </h3>
          <div className="flex flex-wrap gap-1.5">
            <Badge data-testid="section-status" variant="outline" className={cn(STATUS_CLASSES[section.status])}>
              {STATUS_LABELS[section.status] ?? section.status}
            </Badge>
            <Badge data-testid="evidence-tier" variant="outline" className={cn(TIER_CLASSES[section.evidence_tier])}>
              {tierLabel(sectionKey, section.evidence_tier)}
            </Badge>
          </div>
        </div>
        {available ? (
          <p data-testid="section-source" className="text-xs text-muted-foreground">
            {sourceLine(section)}
          </p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {available ? (
          children
        ) : (
          <p data-testid="section-reason" className="text-muted-foreground">
            {section.status_reason}
          </p>
        )}
        {section.evidence_note ? (
          <p data-testid="evidence-note" className="text-xs text-muted-foreground">
            {section.evidence_note}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SectionBody({ sectionKey, sections }: { sectionKey: ContentSectionKey; sections: Sections }) {
  switch (sectionKey) {
    case "documents":
      return <DocumentsBody data={sections.documents.data} />;
    case "health":
      return <HealthBody data={sections.health.data} />;
    case "missing_evidence":
      return <MissingEvidenceBody data={sections.missing_evidence.data} />;
    case "coherence":
      return <CoherenceBody data={sections.coherence.data} />;
    case "alerts":
      return <AlertsBody data={sections.alerts.data} />;
    case "hitl":
      return <HitlBody data={sections.hitl.data} />;
    case "budget":
      return <BudgetBody data={sections.budget.data} />;
    case "wbs":
      return <WbsBody data={sections.wbs.data} />;
    case "stakeholders":
      return <StakeholdersBody data={sections.stakeholders.data} />;
    case "raci":
      return <RaciBody data={sections.raci.data} />;
    default:
      return null;
  }
}

function Counts({
  counts,
  label = humanize,
}: {
  counts: Record<string, number>;
  label?: (key: string) => string;
}) {
  const entries = Object.entries(counts);
  if (entries.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([key, count]) => (
        <Badge key={key} variant="secondary">
          {label(key)}: {count}
        </Badge>
      ))}
    </div>
  );
}

function Note({ testId, children }: { testId?: string; children: ReactNode }) {
  return (
    <p data-testid={testId} className="rounded-md bg-muted/40 px-2 py-1 text-xs text-muted-foreground">
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Section bodies
// ---------------------------------------------------------------------------

type SectionData<K extends keyof Sections> = Sections[K]["data"];

function DocumentsBody({ data }: { data: SectionData<"documents"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        <span className="text-lg font-semibold">{data.total}</span> document(s)
      </p>
      <Counts counts={data.by_processing_status} label={documentStatusLabel} />
      {data.counts_are_partial ? (
        <Note testId="partial-note">Counts cover the documents that could be loaded, not all {data.total}.</Note>
      ) : null}
      <ul className="divide-y">
        {data.items.map((document) => (
          <li key={document.id} className="flex flex-wrap justify-between gap-2 py-1.5">
            <span className="font-medium">{document.filename}</span>
            <span className="text-muted-foreground">
              {humanize(document.document_type)} · {documentStatusLabel(document.processing_status)}
              {document.version > 1 ? ` · v${document.version}` : ""}
            </span>
          </li>
        ))}
      </ul>
      {data.truncated ? <Note>Showing the first {data.items.length} documents.</Note> : null}
    </>
  );
}

function HealthBody({ data }: { data: SectionData<"health"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        Composite:{" "}
        <span className="font-semibold">
          {data.composite_score === null || data.composite_score === undefined
            ? UNKNOWN_LABEL
            : `${formatScore(data.composite_score)} (${humanize(data.composite_band)})`}
        </span>
      </p>
      <ul className="space-y-2">
        {data.dimensions.map((dimension) => (
          <li key={dimension.dimension} className="rounded-md border p-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">{humanize(dimension.dimension)}</span>
              <span>
                {dimension.score === null || dimension.score === undefined
                  ? UNKNOWN_LABEL
                  : `${formatScore(dimension.score)} · ${humanize(dimension.band)} · confidence ${Math.round(
                      dimension.confidence * 100,
                    )}%`}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {dimension.evidence_count > 0 ? `${dimension.evidence_count} evidence reference(s)` : "No evidence cited"}
            </p>
            {(dimension.missing_data ?? []).length > 0 ? (
              <p className="text-xs text-muted-foreground">Missing: {(dimension.missing_data ?? []).join("; ")}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </>
  );
}

function MissingEvidenceBody({ data }: { data: SectionData<"missing_evidence"> }) {
  if (!data) return null;
  return (
    <ul className="list-disc space-y-1 pl-5">
      {data.items.map((gap) => (
        <li key={`${gap.source_domain}-${gap.subject}-${gap.description}`}>
          <span className="text-muted-foreground">
            {sectionLabel(gap.source_domain)} · {humanize(gap.subject)}:
          </span>{" "}
          {gap.description}
        </li>
      ))}
    </ul>
  );
}

function CoherenceBody({ data }: { data: SectionData<"coherence"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        Score: <span className="font-semibold">{formatScore(data.score)}</span>
        {data.score_version ? <span className="text-muted-foreground"> · {data.score_version}</span> : null}
      </p>
      {data.score_reason ? <p className="text-muted-foreground">Reason: {humanize(data.score_reason)}</p> : null}
      {(data.missing_dimensions ?? []).length > 0 ? (
        <p className="text-muted-foreground">
          Missing evidence for: {(data.missing_dimensions ?? []).map(humanize).join(", ")}
        </p>
      ) : null}
      <p className="text-muted-foreground">Findings in the latest evaluation: {data.evaluation_alert_count}</p>
      {data.last_activity_at ? (
        <p className="text-xs text-muted-foreground">
          Latest project activity considered: {formatDateTime(data.last_activity_at)}
        </p>
      ) : null}
    </>
  );
}

function AlertsBody({ data }: { data: SectionData<"alerts"> }) {
  if (!data) return null;
  const closed = data.total - data.open_count;
  return (
    <>
      <p>
        <span className="text-lg font-semibold">{data.open_count}</span> open · {closed} closed
        {data.overdue_open_count > 0 ? (
          <span className="text-amber-700 dark:text-amber-300"> · {data.overdue_open_count} past SLA</span>
        ) : null}
      </p>
      <Counts counts={data.open_by_severity} />
      <ul className="divide-y">
        {data.items.map((alert) => (
          <li key={alert.id} data-testid="alert-row" className="space-y-1 py-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary">{humanize(alert.severity)}</Badge>
              {alert.overdue ? (
                <Badge variant="outline" className={cn(LEVEL_CLASSES.warning)}>
                  Overdue
                </Badge>
              ) : null}
              <span className="font-medium">{alert.title}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              {humanize(alert.category)} · raised {formatDate(alert.created_at)}
              {alert.sla_due_at ? ` · respond by ${formatDateTime(alert.sla_due_at)}` : ""} ·{" "}
              {TIER_LABELS[alert.evidence_tier] ?? alert.evidence_tier}
            </p>
          </li>
        ))}
      </ul>
      {data.truncated ? <Note>Showing the first {data.items.length} open alerts.</Note> : null}
    </>
  );
}

function HitlBody({ data }: { data: SectionData<"hitl"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        <span className="text-lg font-semibold">{data.pending_count}</span> awaiting a decision
      </p>
      <p data-testid="hitl-overdue" className="text-muted-foreground">
        Past deadline:{" "}
        {data.overdue_count === null || data.overdue_count === undefined
          ? "Unknown (not every pending item could be loaded)"
          : data.overdue_count}
      </p>
      <ul className="divide-y">
        {data.items.map((review) => (
          <li key={review.item_id} className="flex flex-wrap justify-between gap-2 py-1.5">
            <span>
              {humanize(review.item_type)} · {humanize(review.impact_level)} impact
            </span>
            <span className={cn("text-muted-foreground", review.overdue && "text-amber-700 dark:text-amber-300")}>
              {review.overdue ? "Overdue · " : ""}due {formatDateTime(review.sla_due_date)}
            </span>
          </li>
        ))}
      </ul>
      {data.truncated ? (
        <Note>
          Showing {data.items.length} of {data.pending_count} items.
        </Note>
      ) : null}
    </>
  );
}

function BudgetBody({ data }: { data: SectionData<"budget"> }) {
  if (!data) return null;
  return (
    <>
      <dl className="grid grid-cols-3 gap-2">
        <Fact label="Total">{formatMoney(data.total_budget, data.currency)}</Fact>
        <div data-testid="budget-spend">
          <Fact label="Spend">
            {data.spend_recorded ? formatMoney(data.spent_amount, data.currency) : "No spend recorded"}
          </Fact>
        </div>
        <div data-testid="budget-remaining">
          <Fact label="Remaining">
            {data.remaining_budget === null || data.remaining_budget === undefined
              ? "Not shown"
              : formatMoney(data.remaining_budget, data.currency)}
          </Fact>
        </div>
      </dl>
      <ul className="divide-y">
        {data.items.map((line) => (
          <li key={line.id} className="flex justify-between gap-2 py-1.5">
            <span>
              <span className="text-muted-foreground">{line.code}</span> {line.name}
            </span>
            <span>{formatMoney(line.amount, data.currency)}</span>
          </li>
        ))}
      </ul>
      {data.notes.map((note) => (
        <Note key={note}>{note}</Note>
      ))}
    </>
  );
}

function WbsBody({ data }: { data: SectionData<"wbs"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        <span className="text-lg font-semibold">{data.item_count}</span> item(s) · {data.root_count} top-level ·{" "}
        {data.leaf_count} leaf · deepest level {data.max_level}
      </p>
      <p data-testid="wbs-coverage" className="text-muted-foreground">
        {data.items_with_budget} of {data.item_count} with a budget · {data.items_with_planned_dates} of{" "}
        {data.item_count} with planned start and end
      </p>
      <Counts counts={data.by_item_type} />
      <ul className="divide-y">
        {data.roots.map((node) => (
          <li key={node.id} className="flex flex-wrap justify-between gap-2 py-1.5">
            <span>
              <span className="text-muted-foreground">{node.code}</span> {node.name}
            </span>
            <span className="text-xs text-muted-foreground">
              {node.item_type ? `${humanize(node.item_type)} · ` : ""}
              {TIER_LABELS[node.evidence_tier] ?? node.evidence_tier}
            </span>
          </li>
        ))}
      </ul>
      {data.truncated ? <Note>Showing the first {data.roots.length} top-level items.</Note> : null}
    </>
  );
}

function StakeholdersBody({ data }: { data: SectionData<"stakeholders"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        <span className="text-lg font-semibold">{data.total}</span> stakeholder(s)
      </p>
      <p data-testid="key-players" className="text-muted-foreground">
        Key players:{" "}
        {data.key_player_count === null || data.key_player_count === undefined
          ? "Unknown (not every stakeholder could be loaded)"
          : data.key_player_count}
      </p>
      <Counts counts={data.by_quadrant} />
      {data.counts_are_partial ? (
        <Note testId="partial-note">Counts cover the stakeholders that could be loaded, not all {data.total}.</Note>
      ) : null}
      <ul className="divide-y">
        {data.items.map((person) => (
          <li key={person.id} className="flex flex-wrap justify-between gap-2 py-1.5">
            <span>
              <span className="font-medium">{person.name ?? "Unnamed"}</span>
              {person.role ? <span className="text-muted-foreground"> · {person.role}</span> : null}
            </span>
            <span className="text-xs text-muted-foreground">
              {TIER_LABELS[person.evidence_tier] ?? person.evidence_tier}
            </span>
          </li>
        ))}
      </ul>
    </>
  );
}

function RaciBody({ data }: { data: SectionData<"raci"> }) {
  if (!data) return null;
  return (
    <>
      <p>
        <span className="text-lg font-semibold">{data.task_count}</span> task(s) · {data.assignment_count}{" "}
        assignment(s) · {data.verified_assignment_count} verified
      </p>
      {data.tasks_without_accountable > 0 ? (
        <p className="text-amber-700 dark:text-amber-300">
          {data.tasks_without_accountable} task(s) without an accountable party
        </p>
      ) : null}
      <ul className="divide-y">
        {data.tasks.map((task) => (
          <li key={task.task_code} className="space-y-0.5 py-1.5">
            <span>
              <span className="text-muted-foreground">{task.task_code}</span> {task.task_name}
            </span>
            <p className="text-xs text-muted-foreground">
              Accountable: {task.accountable.length > 0 ? task.accountable.join(", ") : "none"} · Responsible:{" "}
              {task.responsible.length > 0 ? task.responsible.join(", ") : "none"}
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}

// ---------------------------------------------------------------------------
// Evidence quality
// ---------------------------------------------------------------------------

function EvidenceQuality({ sections }: { sections: Sections }) {
  const data = sections.evidence_quality.data;
  if (!data) return null;
  return (
    <Card data-testid="evidence-quality" aria-labelledby="evidence-quality-heading" className="print:break-inside-avoid">
      <CardHeader>
        <h3 id="evidence-quality-heading" className={HEADING_CLASS}>
          Evidence quality
        </h3>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b text-xs uppercase text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Section
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Status
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Source link
                </th>
                <th scope="col" className="py-2 pr-3 font-medium">
                  Why
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.section_key} data-testid="evidence-quality-row" className="border-b last:border-b-0">
                  <td className="py-2 pr-3">{sectionLabel(row.section_key)}</td>
                  <td className="py-2 pr-3">{STATUS_LABELS[row.status] ?? row.status}</td>
                  <td className="py-2 pr-3">{tierLabel(row.section_key, row.evidence_tier)}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{row.evidence_note ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
