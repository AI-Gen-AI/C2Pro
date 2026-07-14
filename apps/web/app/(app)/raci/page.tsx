'use client';

import { useEffect, useMemo, useState } from 'react';
import { env } from '@/config/env';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Search, Download, Sparkles } from 'lucide-react';
import { useRaci, type RaciRow } from '@/hooks/useRaci';
import { useProjects } from '@/hooks/useProjects';
import type { ProjectListItem } from '@/lib/api/contracts';

type RaciTemplate = {
  id: string;
  name: string;
  summary: string;
  governanceFocus: string;
  defaultActivities: string[];
  stakeholderTracks: string[];
};

type AutoAssignGoal = 'rebalance' | 'clarify' | 'expedite';

type AutoAssignSuggestion = {
  activity: string;
  rationale: string;
  changes: Partial<RaciRow>;
};

const raciTypes = {
  R: { label: 'Responsible', color: 'bg-blue-100 text-blue-700' },
  A: { label: 'Accountable', color: 'bg-green-100 text-green-700' },
  C: { label: 'Consulted', color: 'bg-yellow-100 text-yellow-700' },
  I: { label: 'Informed', color: 'bg-gray-100 text-gray-700' },
};

const RACI_TEMPLATES: RaciTemplate[] = [
  {
    id: 'epc-megaproject',
    name: 'EPC Megaproject',
    summary: 'Coordinate multi-package engineering, procurement, and construction accountability.',
    governanceFocus: 'Integrated package delivery',
    defaultActivities: ['Package Award', 'Design Freeze', 'Field Coordination'],
    stakeholderTracks: ['Commercial Board', 'Delivery PMO', 'Contractor Steering'],
  },
  {
    id: 'industrial-retrofit',
    name: 'Industrial Retrofit',
    summary: 'Balance shutdown planning, safety controls, and phased execution ownership.',
    governanceFocus: 'Shutdown readiness and execution',
    defaultActivities: ['Turnaround Planning', 'Isolation Review', 'Commissioning Gate'],
    stakeholderTracks: ['Plant Operations', 'Maintenance Lead', 'Safety Cell'],
  },
  {
    id: 'public-infrastructure',
    name: 'Public Infrastructure',
    summary: 'Deploy a governance-ready RACI model for regulated delivery programs.',
    governanceFocus: 'Public approvals and stakeholder traceability',
    defaultActivities: ['Permit Control', 'Funding Review', 'Community Review'],
    stakeholderTracks: ['Owner Representative', 'Regulatory Affairs', 'Public Liaison'],
  },
];

function formatTimelineDate(value?: string | null): string {
  if (!value) {
    return 'Unscheduled';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Unscheduled';
  }

  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function buildTimelineRows(
  rows: ReturnType<typeof useRaci>['data'],
): Array<{
  activity: string;
  phaseLabel: string;
  scheduleLabel: string;
  offset: number;
  width: number;
}> {
  if (rows.length === 0) {
    return [];
  }

  const normalized = rows.map((row, index) => ({
    activity: row.activity,
    sequenceIndex: row.sequenceIndex ?? index + 1,
    taskCode: row.taskCode ?? `T-${index + 1}`,
    plannedStart: row.plannedStart ?? null,
    plannedEnd: row.plannedEnd ?? null,
  }));

  const datedRows = normalized.filter((row) => row.plannedStart && row.plannedEnd);
  const anchorMs =
    datedRows.length > 0
      ? Math.min(...datedRows.map((row) => new Date(row.plannedStart as string).getTime()))
      : null;
  const maxEndMs =
    datedRows.length > 0
      ? Math.max(...datedRows.map((row) => new Date(row.plannedEnd as string).getTime()))
      : null;
  const totalDurationMs =
    anchorMs !== null && maxEndMs !== null ? Math.max(maxEndMs - anchorMs, 24 * 60 * 60 * 1000) : null;

  return normalized.map((row, index) => {
    const startMs = row.plannedStart ? new Date(row.plannedStart).getTime() : null;
    const endMs = row.plannedEnd ? new Date(row.plannedEnd).getTime() : null;
    const hasSchedule =
      startMs !== null &&
      endMs !== null &&
      !Number.isNaN(startMs) &&
      !Number.isNaN(endMs) &&
      anchorMs !== null &&
      totalDurationMs !== null;

    const offset = hasSchedule ? ((startMs - anchorMs) / totalDurationMs) * 100 : index * 18;
    const width = hasSchedule
      ? Math.max(((endMs - startMs) / totalDurationMs) * 100, 12)
      : 32 + (index % 3) * 12;

    return {
      activity: row.activity,
      phaseLabel: `Sequence ${row.sequenceIndex} · ${row.taskCode}`,
      scheduleLabel: `${formatTimelineDate(row.plannedStart)} to ${formatTimelineDate(row.plannedEnd)}`,
      offset,
      width,
    };
  });
}

function areRaciRowsEqual(left: RaciRow[], right: RaciRow[]): boolean {
  if (left.length !== right.length) {
    return false;
  }

  return left.every((row, index) => {
    const candidate = right[index];
    return (
      row.activity === candidate?.activity &&
      row.projectManager === candidate?.projectManager &&
      row.technicalLead === candidate?.technicalLead &&
      row.stakeholder === candidate?.stakeholder &&
      row.contractor === candidate?.contractor &&
      row.sequenceIndex === candidate?.sequenceIndex &&
      row.taskCode === candidate?.taskCode &&
      row.plannedStart === candidate?.plannedStart &&
      row.plannedEnd === candidate?.plannedEnd &&
      row.projectId === candidate?.projectId
    );
  });
}

function getFieldLabel(field: keyof Pick<RaciRow, 'projectManager' | 'technicalLead' | 'stakeholder' | 'contractor'>): string {
  switch (field) {
    case 'projectManager':
      return 'Project Manager';
    case 'technicalLead':
      return 'Technical Lead';
    case 'stakeholder':
      return 'Stakeholder';
    case 'contractor':
      return 'Contractor';
  }
}

function buildAutoAssignSuggestions(
  rows: RaciRow[],
  goal: AutoAssignGoal,
  busiestLane: string,
): AutoAssignSuggestion[] {
  const overloadedField =
    busiestLane === 'Project Manager'
      ? 'projectManager'
      : busiestLane === 'Technical Lead'
        ? 'technicalLead'
        : busiestLane === 'Stakeholder'
          ? 'stakeholder'
          : busiestLane === 'Contractor'
            ? 'contractor'
            : null;

  if (!overloadedField) {
    return [];
  }

  const alternatives: Array<keyof Pick<RaciRow, 'projectManager' | 'technicalLead' | 'stakeholder' | 'contractor'>> =
    ['projectManager', 'technicalLead', 'stakeholder', 'contractor'].filter(
      (field) => field !== overloadedField,
    ) as Array<keyof Pick<RaciRow, 'projectManager' | 'technicalLead' | 'stakeholder' | 'contractor'>>;

  return rows.flatMap((row) => {
    const currentValue = row[overloadedField];

    if (goal === 'clarify') {
      const hasAccountable = [row.projectManager, row.technicalLead, row.stakeholder, row.contractor].includes('A');
      if (!hasAccountable) {
        return [
          {
            activity: row.activity,
            rationale: `Add a single accountable owner to ${row.activity} for cleaner approval governance.`,
            changes: { projectManager: 'A' },
          },
        ];
      }

      return [];
    }

    if (goal === 'expedite') {
      if (row.contractor === '' || row.contractor === 'I') {
        return [
          {
            activity: row.activity,
            rationale: `Promote contractor execution ownership on ${row.activity} to reduce handoff lag.`,
            changes: {
              contractor: 'R',
              stakeholder: row.stakeholder === 'R' ? 'C' : row.stakeholder || 'C',
            },
          },
        ];
      }

      return [];
    }

    if (currentValue !== 'A' && currentValue !== 'R') {
      return [];
    }

    const targetField = alternatives.find((field) => row[field] === '' || row[field] === 'I' || row[field] === 'C');
    if (!targetField) {
      return [];
    }

    const reassignedRole = currentValue;
    const retainedRole = currentValue === 'A' ? 'C' : 'I';

    return [
      {
        activity: row.activity,
        rationale: `Move ${currentValue === 'A' ? 'accountable' : 'responsible'} ownership for ${row.activity} from ${getFieldLabel(overloadedField)} to ${getFieldLabel(targetField)} to rebalance the busiest lane.`,
        changes: {
          [overloadedField]: retainedRole,
          [targetField]: reassignedRole,
        },
      },
    ];
  });
}

export default function RaciPage() {
  const [projectFilter, setProjectFilter] = useState('all');
  const [viewMode, setViewMode] = useState<'matrix' | 'list' | 'timeline'>('matrix');
  const { data: raciData, loading, error } = useRaci(
    projectFilter === 'all' ? undefined : projectFilter,
  );
  const { data: projects } = useProjects(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState(RACI_TEMPLATES[0]?.id ?? '');
  const [autoAssignDialogOpen, setAutoAssignDialogOpen] = useState(false);
  const [autoAssignGoal, setAutoAssignGoal] = useState<AutoAssignGoal>('rebalance');
  const [autoAssignSuggestions, setAutoAssignSuggestions] = useState<AutoAssignSuggestion[]>([]);
  const [raciRows, setRaciRows] = useState<RaciRow[]>([]);
  const [autoAssignSummary, setAutoAssignSummary] = useState<string | null>(null);

  if (!env.FEATURE_RACI_GENERATION) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">RACI Matrix</h1>
        <div className="rounded-2xl border border-border/70 bg-muted/20 p-6 text-sm text-muted-foreground">
          RACI generation is not enabled in this environment yet.
        </div>
      </div>
    );
  }

  const selectedTemplate =
    RACI_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    RACI_TEMPLATES[0];

  useEffect(() => {
    setRaciRows((currentRows) =>
      areRaciRowsEqual(currentRows, raciData) ? currentRows : raciData,
    );
  }, [raciData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading RACI matrix…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {error.message}
      </div>
    );
  }

  const filteredData = raciRows.filter((row) =>
    row.activity.toLowerCase().includes(searchQuery.toLowerCase())
  );
  const workloadAnalysis = useMemo(() => {
    const stakeholderColumns = [
      { key: 'projectManager', label: 'Project Manager' },
      { key: 'technicalLead', label: 'Technical Lead' },
      { key: 'stakeholder', label: 'Stakeholder' },
      { key: 'contractor', label: 'Contractor' },
    ] as const;
    const loadWeights: Record<string, number> = {
      A: 4,
      R: 3,
      C: 1,
      I: 1,
    };

    const rows = filteredData.map((row) => ({
      activity: row.activity,
      projectManager: row.projectManager,
      technicalLead: row.technicalLead,
      stakeholder: row.stakeholder,
      contractor: row.contractor,
    }));

    const metrics = stakeholderColumns.map(({ key, label }) => {
      let assignments = 0;
      let load = 0;

      rows.forEach((row) => {
        const role = String(row[key] ?? '').trim();
        if (!role) {
          return;
        }

        assignments += 1;
        load += loadWeights[role] ?? 0;
      });

      return { label, assignments, load };
    });

    const busiestLane = [...metrics].sort((left, right) => right.load - left.load)[0];

    return {
      metrics,
      busiestLane: busiestLane?.label ?? 'No active workload',
    };
  }, [filteredData]);
  const overloadConflicts = useMemo(() => {
    const overloaded = workloadAnalysis.metrics.filter((metric) => metric.load >= 9);

    return {
      overloaded,
      summary:
        overloaded.length === 1
          ? '1 overloaded stakeholder lane'
          : `${overloaded.length} overloaded stakeholder lanes`,
      recommendation:
        overloaded.length > 0
          ? `Focus the next rebalance on ${overloaded[0]?.label ?? 'overloaded'} assignments.`
          : 'No overloaded stakeholder lanes detected in the current scope.',
    };
  }, [workloadAnalysis.metrics]);
  const timelineRows = useMemo(() => buildTimelineRows(filteredData), [filteredData]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RACI Matrix</h1>
          <p className="text-muted-foreground">
            Define roles and responsibilities for project activities
          </p>
          {autoAssignSummary ? (
            <p className="mt-2 text-sm text-muted-foreground">{autoAssignSummary}</p>
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setTemplateDialogOpen(true)}>
            RACI Templates
          </Button>
          <Button variant="outline" onClick={() => setAutoAssignDialogOpen(true)}>
            <Sparkles className="mr-2 h-4 w-4" />
            Auto-Assign AI
          </Button>
          <Button variant="outline">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button>
            + Add Activity
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search activities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={projectFilter} onValueChange={setProjectFilter}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="All Projects" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Projects</SelectItem>
            {(projects ?? []).map((project: ProjectListItem) => (
              <SelectItem key={project.id} value={project.id}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant={viewMode === 'matrix' ? 'default' : 'outline'}
            onClick={() => setViewMode('matrix')}
          >
            Matrix View
          </Button>
          <Button
            type="button"
            variant={viewMode === 'list' ? 'default' : 'outline'}
            onClick={() => setViewMode('list')}
          >
            List View
          </Button>
          <Button
            type="button"
            variant={viewMode === 'timeline' ? 'default' : 'outline'}
            onClick={() => setViewMode('timeline')}
          >
            Timeline View
          </Button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 rounded-lg border bg-card p-4">
        <span className="text-sm font-medium">Legend:</span>
        {Object.entries(raciTypes).map(([key, { label, color }]) => (
          <div key={key} className="flex items-center gap-2">
            <Badge className={color}>{key}</Badge>
            <span className="text-sm text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>

      <section className="rounded-lg border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Workload Analysis</h2>
            <p className="text-sm text-muted-foreground">
              Busiest lane: {workloadAnalysis.busiestLane}
            </p>
          </div>
          <Badge variant="outline">{filteredData.length} activities in scope</Badge>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {workloadAnalysis.metrics.map((metric) => (
            <div key={metric.label} className="rounded-lg border bg-muted/20 p-4">
              <div className="text-sm font-semibold text-foreground">{metric.label}</div>
              <div className="mt-2 text-sm text-muted-foreground">
                {metric.assignments} assignments · load {metric.load}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">Conflict Detection</h2>
            <p className="text-sm text-muted-foreground">{overloadConflicts.summary}</p>
          </div>
          <Badge variant={overloadConflicts.overloaded.length > 0 ? 'destructive' : 'outline'}>
            {overloadConflicts.overloaded.length > 0 ? 'Needs rebalance' : 'Balanced'}
          </Badge>
        </div>

        <div className="mt-4 space-y-3">
          {overloadConflicts.overloaded.length > 0 ? (
            <>
              {overloadConflicts.overloaded.map((metric) => (
                <div key={metric.label} className="rounded-lg border bg-red-50/60 p-4">
                  <div className="text-sm font-semibold text-red-900">{metric.label}</div>
                  <div className="mt-1 text-sm text-red-800">
                    {metric.label} exceeds the safe workload threshold with load {metric.load}.
                  </div>
                </div>
              ))}
              <p className="text-sm text-muted-foreground">
                {overloadConflicts.recommendation}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              {overloadConflicts.recommendation}
            </p>
          )}
        </div>
      </section>

      {viewMode === 'timeline' ? (
        <section className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Gantt Timeline View</h2>
              <p className="text-sm text-muted-foreground">
                Sequenced activity lanes grounded in API schedule dates and task ordering.
              </p>
            </div>
            <Badge variant="outline">{timelineRows.length} timeline lanes</Badge>
          </div>

          <div className="mt-4 space-y-3">
            {timelineRows.map((row) => (
              <div key={row.activity} className="grid gap-2 md:grid-cols-[220px_1fr] md:items-center">
                <div>
                  <div className="font-medium text-foreground">{row.activity}</div>
                  <div className="text-sm text-muted-foreground">{row.phaseLabel}</div>
                  <div className="text-xs text-muted-foreground">{row.scheduleLabel}</div>
                </div>
                <div className="relative h-10 rounded-full bg-muted/50">
                  <div
                    className="absolute top-2 h-6 rounded-full bg-slate-900"
                    style={{
                      left: `${row.offset}%`,
                      width: `${Math.min(row.width, 90 - row.offset)}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : viewMode === 'list' ? (
        <section className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold tracking-tight">Mobile List View</h2>
              <p className="text-sm text-muted-foreground">
                Activity cards optimized for narrow-screen review.
              </p>
            </div>
            <Badge variant="outline">{filteredData.length} activity cards</Badge>
          </div>

          <div className="mt-4 space-y-3">
            {filteredData.map((row, index) => (
              <div key={`${row.activity}-${index}`} className="rounded-lg border bg-muted/20 p-4">
                <div className="font-semibold text-foreground">{row.activity}</div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <div className="text-sm text-muted-foreground">
                    Project Manager · {row.projectManager || '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Technical Lead · {row.technicalLead || '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Stakeholder · {row.stakeholder || '-'}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    Contractor · {row.contractor || '-'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : (
        <div className="rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Activity
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium">
                    Project Manager
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium">
                    Technical Lead
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium">
                    Stakeholder
                  </th>
                  <th className="px-4 py-3 text-center text-sm font-medium">
                    Contractor
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredData.map((row, index) => (
                  <tr key={index} className="hover:bg-muted/50 transition-colors">
                    <td className="px-4 py-3 font-medium">{row.activity}</td>
                    <td className="px-4 py-3 text-center">
                      <Badge
                        className={
                          raciTypes[row.projectManager as keyof typeof raciTypes]
                            ?.color
                        }
                      >
                        {row.projectManager}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge
                        className={
                          raciTypes[row.technicalLead as keyof typeof raciTypes]
                            ?.color
                        }
                      >
                        {row.technicalLead}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge
                        className={
                          raciTypes[row.stakeholder as keyof typeof raciTypes]
                            ?.color
                        }
                      >
                        {row.stakeholder}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <Badge
                        className={
                          raciTypes[row.contractor as keyof typeof raciTypes]?.color
                        }
                      >
                        {row.contractor}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Dialog open={templateDialogOpen} onOpenChange={setTemplateDialogOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>RACI Templates</DialogTitle>
            <DialogDescription>
              Start from a project-type responsibility template
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-[1.05fr_1.45fr]">
            <div className="space-y-2">
              {RACI_TEMPLATES.map((template) => {
                const isActive = template.id === selectedTemplate?.id;
                return (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => setSelectedTemplateId(template.id)}
                    className={`w-full rounded-lg border p-4 text-left transition-colors ${
                      isActive
                        ? 'border-slate-900 bg-slate-950 text-white'
                        : 'border-border bg-background hover:bg-muted/70'
                    }`}
                  >
                    <div className="text-sm font-semibold">{template.name}</div>
                    <div
                      className={`mt-2 text-xs ${
                        isActive ? 'text-slate-200' : 'text-muted-foreground'
                      }`}
                    >
                      {template.governanceFocus}
                    </div>
                  </button>
                );
              })}
            </div>

            {selectedTemplate ? (
              <section className="rounded-xl border bg-muted/30 p-5">
                <h2 className="text-lg font-semibold tracking-tight">
                  {selectedTemplate.name}
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  {selectedTemplate.summary}
                </p>

                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Governance Focus
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedTemplate.governanceFocus}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Stakeholder Tracks
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTemplate.stakeholderTracks.map((track) => (
                        <Badge key={track} variant="secondary">
                          {track}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Default Activities
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedTemplate.defaultActivities.map((activity) => (
                      <Badge key={activity} variant="outline">
                        {activity}
                      </Badge>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTemplateDialogOpen(false)}>
              Close
            </Button>
            <Button onClick={() => setTemplateDialogOpen(false)}>
              Use Template
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={autoAssignDialogOpen}
        onOpenChange={(open) => {
          setAutoAssignDialogOpen(open);
          if (!open) {
            setAutoAssignSuggestions([]);
          }
        }}
      >
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>AI Auto-Assign</DialogTitle>
            <DialogDescription>
              Generate workload-aware responsibility suggestions from the live RACI matrix.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-5">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Activities in scope
                </div>
                <div className="mt-2 text-2xl font-semibold">{filteredData.length}</div>
              </div>
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Busiest lane
                </div>
                <div className="mt-2 text-lg font-semibold">{workloadAnalysis.busiestLane}</div>
              </div>
              <div className="rounded-lg border bg-muted/30 p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Conflict state
                </div>
                <div className="mt-2 text-sm font-medium">{overloadConflicts.summary}</div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="auto-assign-goal">
                Optimization goal
              </label>
              <Select
                value={autoAssignGoal}
                onValueChange={(value) => setAutoAssignGoal(value as AutoAssignGoal)}
              >
                <SelectTrigger id="auto-assign-goal" className="w-full">
                  <SelectValue placeholder="Choose optimization goal" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rebalance">Balanced workload reassignment</SelectItem>
                  <SelectItem value="clarify">Clarify single accountable owners</SelectItem>
                  <SelectItem value="expedite">Expedite field execution handoffs</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {autoAssignSuggestions.length > 0 ? (
              <div className="space-y-3">
                {autoAssignSuggestions.map((suggestion) => (
                  <div key={suggestion.activity} className="rounded-lg border bg-muted/20 p-4">
                    <div className="font-semibold text-foreground">{suggestion.activity}</div>
                    <div className="mt-2 text-sm text-muted-foreground">{suggestion.rationale}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed bg-muted/20 p-4 text-sm text-muted-foreground">
                {workloadAnalysis.busiestLane} is the current rebalance target. Generate suggestions to preview AI-guided role changes before applying them.
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setAutoAssignDialogOpen(false)}>
              Close
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                setAutoAssignSuggestions(
                  buildAutoAssignSuggestions(filteredData, autoAssignGoal, workloadAnalysis.busiestLane),
                )
              }
            >
              Generate Suggestions
            </Button>
            <Button
              disabled={autoAssignSuggestions.length === 0}
              onClick={() => {
                setRaciRows((prev) =>
                  prev.map((row) => {
                    const suggestion = autoAssignSuggestions.find(
                      (item) => item.activity === row.activity,
                    );
                    return suggestion ? { ...row, ...suggestion.changes } : row;
                  }),
                );
                setAutoAssignSummary(
                  `AI suggestions applied to ${autoAssignSuggestions.length} activities. ${
                    autoAssignGoal === 'rebalance'
                      ? 'Balanced workload reassignment'
                      : autoAssignGoal === 'clarify'
                        ? 'Accountability clarified'
                        : 'Execution handoffs accelerated'
                  }`,
                );
                setAutoAssignDialogOpen(false);
                setAutoAssignSuggestions([]);
              }}
            >
              Apply Suggestions
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
