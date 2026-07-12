'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  bulkResolveAlerts,
  getAlertWorkspaceSettings,
  saveAlertWorkspaceSettings,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
import { statusToToken, severityToToken } from '@/lib/ui/severity-tokens';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
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
import { Checkbox } from '@/components/ui/checkbox';
import { Eye, Check, Search } from 'lucide-react';
import { useAlerts } from '@/hooks/useAlerts';

type AlertTemplate = {
  id: string;
  name: string;
  summary: string;
  responseWindow: string;
  owners: string[];
  assets: string[];
};

type AlertRuleConfig = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  threshold: number;
  severity: 'Critical' | 'High' | 'Medium';
};

type AlertSubscriptionConfig = {
  emailEnabled: boolean;
  emailAddress: string;
  slackEnabled: boolean;
  slackChannel: string;
};

type AlertWithSla = {
  dueAt: Date | null;
  statusLabel: string;
  tone: string;
};

type AlertRecord = {
  id: string;
  project_id?: string;
  severity: string;
  type: string;
  title: string;
  description: string;
  project: string;
  status: string;
  sla_due_at?: string | null;
  sla_policy_name?: string | null;
  created_at?: string;
  createdAt?: string;
};

const ALERT_TEMPLATES: AlertTemplate[] = [
  {
    id: 'executive-escalation',
    name: 'Executive Escalation',
    summary: 'Escalate critical alert clusters for executive response and decision support.',
    responseWindow: 'First response in 2 hours',
    owners: ['Program Director', 'Claims Lead', 'Commercial Control'],
    assets: ['Board Brief', 'Mitigation Timeline', 'Decision Memo'],
  },
  {
    id: 'compliance-sweep',
    name: 'Compliance Sweep',
    summary: 'Prepare a cross-project compliance remediation review.',
    responseWindow: 'Same-day regulatory checkpoint',
    owners: ['Compliance Lead', 'Document Control', 'Site Operations'],
    assets: ['Coverage Audit', 'Regulatory Log', 'Corrective Action Pack'],
  },
  {
    id: 'sla-recovery',
    name: 'SLA Recovery',
    summary: 'Coordinate service recovery for operational alerts that threaten delivery commitments.',
    responseWindow: 'Recovery plan within 4 hours',
    owners: ['Operations Manager', 'Vendor Lead', 'Customer Success'],
    assets: ['Recovery Board', 'Escalation Matrix', 'Service Notes'],
  },
];

const DEFAULT_ALERT_RULES: AlertRuleConfig[] = [
  {
    id: 'schedule-drift',
    name: 'Schedule Drift',
    description: 'Flag delivery plans that move beyond the accepted response window.',
    enabled: true,
    threshold: 7,
    severity: 'Critical',
  },
  {
    id: 'budget-deviation',
    name: 'Budget Deviation',
    description: 'Raise an alert when committed cost exposure exceeds the allowed variance.',
    enabled: true,
    threshold: 10,
    severity: 'High',
  },
  {
    id: 'approval-gap',
    name: 'Approval Gap',
    description: 'Escalate missing ownership or sign-off on required workflow gates.',
    enabled: true,
    threshold: 3,
    severity: 'Medium',
  },
];

const DEFAULT_ALERT_SUBSCRIPTIONS: AlertSubscriptionConfig = {
  emailEnabled: false,
  emailAddress: '',
  slackEnabled: false,
  slackChannel: '',
};

function getMinNotesLength(severity: string): number {
  switch (severity) {
    case 'Critical':
      return 50;
    case 'High':
      return 20;
    case 'Medium':
      return 10;
    default:
      return 0;
  }
}

function requiresCheckbox(severity: string): boolean {
  return severity === 'Critical' || severity === 'High';
}

function requiresRootCause(severity: string): boolean {
  return severity === 'Critical' || severity === 'High';
}

function formatUtcDate(value: Date): string {
  const year = value.getUTCFullYear();
  const month = String(value.getUTCMonth() + 1).padStart(2, '0');
  const day = String(value.getUTCDate()).padStart(2, '0');
  const hours = String(value.getUTCHours()).padStart(2, '0');
  const minutes = String(value.getUTCMinutes()).padStart(2, '0');

  return `${year}-${month}-${day} ${hours}:${minutes} UTC`;
}

function getAlertSla(alert: Record<string, unknown>): AlertWithSla {
  const dueAtValue = typeof alert.sla_due_at === 'string' ? alert.sla_due_at : null;
  const dueAt = dueAtValue ? new Date(dueAtValue) : null;

  if (!dueAt || Number.isNaN(dueAt.getTime())) {
    return {
      dueAt: null,
      statusLabel: 'SLA pending timestamp',
      tone: 'bg-muted text-muted-foreground',
    };
  }

  const status = String(alert.status ?? '');
  if (status === 'Resolved') {
    return {
      dueAt,
      statusLabel: 'Resolved within SLA',
      tone: 'bg-green-100 text-green-700',
    };
  }

  const overdueMs = Date.now() - dueAt.getTime();
  if (overdueMs > 0) {
    const overdueHours = Math.floor(overdueMs / (60 * 60 * 1000));
    return {
      dueAt,
      statusLabel: `Overdue by ${overdueHours}h`,
      tone: 'bg-red-100 text-red-700',
    };
  }

  return {
    dueAt,
    statusLabel: `Due ${formatUtcDate(dueAt)}`,
    tone: 'bg-amber-100 text-amber-800',
  };
}

export default function AlertsPage() {
  const { alerts, loading, error } = useAlerts();
  const [alertsState, setAlertsState] = useState<AlertRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [projectFilter, setProjectFilter] = useState('All Projects');
  const [typeFilter, setTypeFilter] = useState('All Types');
  const [severityFilter, setSeverityFilter] = useState('All Severity');
  const [statusFilter, setStatusFilter] = useState('All Status');
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [rulesDialogOpen, setRulesDialogOpen] = useState(false);
  const [subscriptionsDialogOpen, setSubscriptionsDialogOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState(ALERT_TEMPLATES[0]?.id ?? '');
  const [alertRules, setAlertRules] = useState<AlertRuleConfig[]>(DEFAULT_ALERT_RULES);
  const [draftAlertRules, setDraftAlertRules] = useState<AlertRuleConfig[]>(DEFAULT_ALERT_RULES);
  const [alertSubscriptions, setAlertSubscriptions] = useState<AlertSubscriptionConfig>({
    emailEnabled: false,
    emailAddress: '',
    slackEnabled: false,
    slackChannel: '',
  });
  const [draftAlertSubscriptions, setDraftAlertSubscriptions] = useState<AlertSubscriptionConfig>({
    emailEnabled: false,
    emailAddress: '',
    slackEnabled: false,
    slackChannel: '',
  });
  const [selectedAlertIds, setSelectedAlertIds] = useState<string[]>([]);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [selectedAlertDetail, setSelectedAlertDetail] = useState<AlertRecord | null>(null);
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<AlertRecord | null>(null);
  const [bulkResolveIds, setBulkResolveIds] = useState<string[]>([]);
  const [resolutionNotes, setResolutionNotes] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [confirmChecked, setConfirmChecked] = useState(false);

  const selectedTemplate =
    ALERT_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    ALERT_TEMPLATES[0];
  const activeRuleCount = useMemo(
    () => alertRules.filter((rule) => rule.enabled).length,
    [alertRules],
  );
  const activeSubscriptionCount = useMemo(() => {
    let total = 0;
    if (alertSubscriptions.emailEnabled && alertSubscriptions.emailAddress.trim()) {
      total += 1;
    }
    if (alertSubscriptions.slackEnabled && alertSubscriptions.slackChannel.trim()) {
      total += 1;
    }
    return total;
  }, [alertSubscriptions]);
  const alertsWithSla = useMemo(
    () =>
      alertsState.map((alert) => ({
        alert,
        sla: getAlertSla(alert as Record<string, unknown>),
      })),
    [alertsState],
  );
  const projectOptions = useMemo(
    () =>
      Array.from(
        new Map(
          alertsState.map((alert) => [
            alert.project_id ?? alert.project,
            {
              value: alert.project_id ?? alert.project,
              label: alert.project_id
                ? `${alert.project} (${alert.project_id})`
                : alert.project,
            },
          ]),
        ).values(),
      ),
    [alertsState],
  );
  const typeOptions = useMemo(
    () => Array.from(new Set(alertsState.map((alert) => alert.type))).sort(),
    [alertsState],
  );

  useEffect(() => {
    setAlertsState(alerts as AlertRecord[]);
  }, [alerts]);

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspaceSettings() {
      try {
        const persisted = await getAlertWorkspaceSettings();
        if (cancelled) {
          return;
        }

        const nextRules =
          persisted?.rules && persisted.rules.length > 0
            ? persisted.rules
            : DEFAULT_ALERT_RULES;
        const nextSubscriptions = persisted?.subscriptions ?? DEFAULT_ALERT_SUBSCRIPTIONS;

        setAlertRules(nextRules);
        setDraftAlertRules(nextRules);
        setAlertSubscriptions(nextSubscriptions);
        setDraftAlertSubscriptions(nextSubscriptions);
      } catch (loadError) {
        console.error('Error loading alert workspace settings:', loadError);
        if (cancelled) {
          return;
        }
        setAlertRules(DEFAULT_ALERT_RULES);
        setDraftAlertRules(DEFAULT_ALERT_RULES);
        setAlertSubscriptions(DEFAULT_ALERT_SUBSCRIPTIONS);
        setDraftAlertSubscriptions(DEFAULT_ALERT_SUBSCRIPTIONS);
      }
    }

    void loadWorkspaceSettings();

    return () => {
      cancelled = true;
    };
  }, []);

  const openRulesDialog = () => {
    setDraftAlertRules(alertRules);
    setRulesDialogOpen(true);
  };

  const saveRules = async () => {
    const persisted = await saveAlertWorkspaceSettings({
      rules: draftAlertRules,
      subscriptions: alertSubscriptions,
    });
    const nextRules = persisted.rules.length > 0 ? persisted.rules : draftAlertRules;
    const nextSubscriptions = persisted.subscriptions ?? draftAlertSubscriptions;
    setAlertRules(nextRules);
    setDraftAlertRules(nextRules);
    setAlertSubscriptions(nextSubscriptions);
    setDraftAlertSubscriptions(nextSubscriptions);
    setRulesDialogOpen(false);
  };

  const openSubscriptionsDialog = () => {
    setDraftAlertSubscriptions(alertSubscriptions);
    setSubscriptionsDialogOpen(true);
  };

  const saveSubscriptions = async () => {
    const persisted = await saveAlertWorkspaceSettings({
      rules: alertRules,
      subscriptions: draftAlertSubscriptions,
    });
    const nextRules = persisted.rules.length > 0 ? persisted.rules : draftAlertRules;
    const nextSubscriptions = persisted.subscriptions ?? draftAlertSubscriptions;
    setAlertRules(nextRules);
    setDraftAlertRules(nextRules);
    setAlertSubscriptions(nextSubscriptions);
    setDraftAlertSubscriptions(nextSubscriptions);
    setSubscriptionsDialogOpen(false);
  };

  const openResolveDialog = (alert: AlertRecord) => {
    setSelectedAlert(alert);
    setBulkResolveIds([]);
    setResolutionNotes('');
    setRootCause('');
    setConfirmChecked(false);
    setResolveDialogOpen(true);
  };

  const toggleAlertSelection = (alertId: string, checked: boolean) => {
    setSelectedAlertIds((current) =>
      checked ? [...new Set([...current, alertId])] : current.filter((id) => id !== alertId),
    );
  };

  const openBulkResolveDialog = () => {
    if (selectedAlertIds.length === 0) {
      return;
    }

    const selectedAlerts = alertsState.filter((alert) => selectedAlertIds.includes(alert.id));
    const highestSeverityAlert =
      selectedAlerts.find((alert) => alert.severity === 'Critical') ??
      selectedAlerts.find((alert) => alert.severity === 'High') ??
      selectedAlerts.find((alert) => alert.severity === 'Medium') ??
      selectedAlerts[0] ??
      null;

    setSelectedAlert(highestSeverityAlert);
    setBulkResolveIds(selectedAlertIds);
    setResolutionNotes('');
    setRootCause('');
    setConfirmChecked(false);
    setResolveDialogOpen(true);
  };

  const openDetailDialog = (alert: AlertRecord) => {
    setSelectedAlertDetail(alert);
    setDetailDialogOpen(true);
  };

  const handleConfirmResolution = async () => {
    if (!selectedAlert) {
      return;
    }

    const targetIds = bulkResolveIds.length > 0 ? bulkResolveIds : [selectedAlert.id];
    if (bulkResolveIds.length > 0) {
      await bulkResolveAlerts({
        alertIds: targetIds,
        resolution: resolutionNotes,
        rootCause: rootCause || null,
      });
    }
    setAlertsState((prev) =>
      prev.map((alert) =>
        targetIds.includes(alert.id) ? { ...alert, status: 'Resolved' } : alert,
      ),
    );
    setSelectedAlertIds((current) => current.filter((id) => !targetIds.includes(id)));
    setResolveDialogOpen(false);
    setSelectedAlert(null);
    setBulkResolveIds([]);
    setResolutionNotes('');
    setRootCause('');
    setConfirmChecked(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading alerts…
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

  const filteredAlerts = alertsWithSla.filter(({ alert }) => {
    const matchesSearch =
      alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.project.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (alert.project_id ?? '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesProject =
      projectFilter === 'All Projects' ||
      alert.project === projectFilter ||
      alert.project_id === projectFilter;
    const matchesType =
      typeFilter === 'All Types' || alert.type === typeFilter;
    const matchesSeverity =
      severityFilter === 'All Severity' || alert.severity === severityFilter;
    const matchesStatus =
      statusFilter === 'All Status' || alert.status === statusFilter;
    return matchesSearch && matchesProject && matchesType && matchesSeverity && matchesStatus;
  });
  const severityCounts = alertsState.reduce<Record<string, number>>((acc, alert) => {
    acc[alert.severity] = (acc[alert.severity] ?? 0) + 1;
    return acc;
  }, {});
  const statusCounts = alertsState.reduce<Record<string, number>>((acc, alert) => {
    acc[alert.status] = (acc[alert.status] ?? 0) + 1;
    return acc;
  }, {});
  const topProjectEntry = Object.entries(
    filteredAlerts.reduce<Record<string, number>>((acc, { alert }) => {
      acc[alert.project] = (acc[alert.project] ?? 0) + 1;
      return acc;
    }, {}),
  ).sort(([, a], [, b]) => b - a)[0];
  const openCount =
    (statusCounts["Open"] ?? 0) + (statusCounts["In Progress"] ?? 0);
  const overdueCount = alertsWithSla.filter(
    ({ alert, sla }) =>
      alert.status !== 'Resolved' && sla.statusLabel.startsWith('Overdue by'),
  ).length;
  const analyticsCards = [
    {
      title: "Critical",
      value: `${severityCounts["Critical"] ?? 0} active`,
      detail: "Highest-severity alerts in current workspace.",
      tone: "border-red-200 bg-red-50/40 text-red-900",
    },
    {
      title: "Open Alerts",
      value: `${openCount} currently require action`,
      detail: "Includes open and in-progress remediation work.",
      tone: "border-slate-200 bg-slate-50/70 text-slate-900",
    },
    {
      title: "Top Impacted Project",
      value: topProjectEntry?.[0] ?? "No alerts in scope",
      detail: topProjectEntry
        ? `${topProjectEntry[1]} alerts in current scope`
        : "Adjust filters to inspect alert concentrations.",
      tone: "border-amber-200 bg-amber-50/40 text-amber-950",
    },
    {
      title: "SLA Violations",
      value: `${overdueCount} overdue`,
      detail: overdueCount
        ? "Alerts that have exceeded the current severity response window."
        : "No active SLA violations in the current workspace scope.",
      tone: "border-rose-200 bg-rose-50/40 text-rose-950",
    },
  ];

  const getSeverityColor = (severity: string) => {
    return severityToToken(severity);
  };

  const getStatusColor = (status: string) => {
    return statusToToken(status);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Alerts Center</h1>
          <p className="text-sm text-muted-foreground">
            Monitor and manage all project alerts
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="rounded-full border bg-background/95 px-3 py-1 text-xs font-medium text-foreground shadow-sm">
              {activeRuleCount} active rules
            </span>
            <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-muted-foreground shadow-sm">
              {activeSubscriptionCount > 0
                ? `${activeSubscriptionCount} active subscriptions`
                : 'No active subscriptions'}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 xl:justify-end">
          <Button variant="outline" className="rounded-xl bg-background/95 shadow-sm" onClick={openSubscriptionsDialog}>
            Subscriptions
          </Button>
          <Button variant="outline" className="rounded-xl bg-background/95 shadow-sm" onClick={openRulesDialog}>
            Alert Rules
          </Button>
          <Button variant="outline" className="rounded-xl bg-background/95 shadow-sm" onClick={() => setTemplateDialogOpen(true)}>
            Alert Templates
          </Button>
          <Button className="rounded-xl shadow-sm">
            + New Alert
          </Button>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-4">
        {analyticsCards.map((card) => (
          <section
            key={card.title}
            className={`rounded-2xl border p-4 shadow-sm backdrop-blur-sm ${card.tone}`}
            aria-label={card.title}
          >
            <div className="text-xs font-semibold uppercase tracking-[0.18em]">
              {card.title}
            </div>
            <div className="mt-3 text-2xl font-semibold tracking-tight">
              {card.value}
            </div>
            <p className="mt-2 text-sm opacity-80">{card.detail}</p>
          </section>
        ))}
      </div>

      {/* Filters */}
      <section className="rounded-2xl border bg-card/80 p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border bg-background/70 p-3 shadow-sm">
        <div className="relative flex-1 min-w-[260px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search alerts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="h-11 rounded-xl border-border/80 bg-background/95 pl-9"
          />
        </div>
        <Select value={projectFilter} onValueChange={setProjectFilter}>
          <SelectTrigger className="h-11 w-[240px] rounded-xl border-border/80 bg-background/95 shadow-sm" aria-label="Project filter">
            <SelectValue placeholder="All Projects" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Projects">All Projects</SelectItem>
            {projectOptions.map((project) => (
              <SelectItem key={project.value} value={project.value}>
                {project.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="h-11 w-[180px] rounded-xl border-border/80 bg-background/95 shadow-sm" aria-label="Type filter">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Types">All Types</SelectItem>
            {typeOptions.map((type) => (
              <SelectItem key={type} value={type}>
                {type}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={severityFilter} onValueChange={setSeverityFilter}>
          <SelectTrigger className="h-11 w-[180px] rounded-xl border-border/80 bg-background/95 shadow-sm" aria-label="Severity filter">
            <SelectValue placeholder="All Severity" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Severity">All Severity</SelectItem>
            <SelectItem value="Critical">Critical</SelectItem>
            <SelectItem value="High">High</SelectItem>
            <SelectItem value="Medium">Medium</SelectItem>
            <SelectItem value="Low">Low</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-11 w-[180px] rounded-xl border-border/80 bg-background/95 shadow-sm" aria-label="Status filter">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Status">All Status</SelectItem>
            <SelectItem value="Open">Open</SelectItem>
            <SelectItem value="In Progress">In Progress</SelectItem>
            <SelectItem value="Resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>
      </div>
      </section>

      {selectedAlertIds.length > 0 ? (
        <section className="flex items-center justify-between rounded-2xl border bg-background/85 px-4 py-3 shadow-sm">
          <div className="text-sm font-medium">
            {selectedAlertIds.length} alerts selected
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" className="rounded-xl bg-background/95 shadow-sm" onClick={() => setSelectedAlertIds([])}>
              Clear Selection
            </Button>
            <Button className="rounded-xl shadow-sm" onClick={openBulkResolveDialog}>Bulk Resolve</Button>
          </div>
        </section>
      ) : null}

      {/* Alerts Table */}
      <div className="overflow-hidden rounded-2xl border bg-card shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/30">
              <tr>
                <th className="w-12 p-4">
                  <Checkbox aria-label="Select all alerts" />
                </th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">ID</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Severity
                </th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Type</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Title</th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Project
                </th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Status
                </th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  SLA
                </th>
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredAlerts.map(({ alert, sla }) => (
                <tr
                  key={alert.id}
                  className="transition-colors hover:bg-muted/20"
                >
                  <td className="p-4">
                    <Checkbox
                      aria-label={`Select alert ${alert.id}`}
                      checked={selectedAlertIds.includes(alert.id)}
                      onCheckedChange={(checked) =>
                        toggleAlertSelection(alert.id, checked === true)
                      }
                    />
                  </td>
                  <td className="px-4 py-4 text-sm text-muted-foreground">
                    {alert.id}
                  </td>
                  <td className="px-4 py-4">
                    <Badge
                      variant="outline"
                      className={`rounded-full border px-2.5 py-1 shadow-sm ${getSeverityColor(alert.severity)}`}
                    >
                      {alert.severity}
                    </Badge>
                  </td>
                  <td className="px-4 py-4 text-sm">{alert.type}</td>
                  <td className="px-4 py-4">
                    <div className="max-w-md">
                      <div className="font-semibold text-foreground">{alert.title}</div>
                      <div className="text-sm text-muted-foreground">
                        {alert.description}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-4 text-sm">
                    <div className="space-y-1">
                      <div>{alert.project}</div>
                      {alert.project_id ? (
                        <div className="text-xs text-muted-foreground">{alert.project_id}</div>
                      ) : null}
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <Badge className={`rounded-full px-2.5 py-1 shadow-sm ${getStatusColor(alert.status)}`}>
                      {alert.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-4">
                    <div className="space-y-1">
                      <Badge className={`rounded-full px-2.5 py-1 shadow-sm ${sla.tone}`}>{sla.statusLabel}</Badge>
                        {sla.dueAt ? (
                          <div className="text-xs text-muted-foreground">
                            Due {formatUtcDate(sla.dueAt)}
                          </div>
                        ) : null}
                        {alert.sla_policy_name ? (
                          <div className="text-xs text-muted-foreground">
                            {alert.sla_policy_name}
                          </div>
                        ) : null}
                      </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl bg-background/95 shadow-sm"
                        aria-label={`View alert ${alert.id}`}
                        onClick={() => openDetailDialog(alert as AlertRecord)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl bg-background/95 shadow-sm"
                        aria-label={`Resolve alert ${alert.id}`}
                        onClick={() => openResolveDialog(alert as AlertRecord)}
                      >
                        <Check className="h-4 w-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <Dialog open={templateDialogOpen} onOpenChange={setTemplateDialogOpen}>
        <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-3xl sm:rounded-2xl">
          <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
            <DialogTitle>Alert Templates</DialogTitle>
            <DialogDescription>
              Start from an alert response template
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-[1.1fr_1.4fr]">
            <div className="space-y-2 rounded-2xl border bg-background/90 p-3 shadow-sm">
              {ALERT_TEMPLATES.map((template) => {
                const isActive = template.id === selectedTemplate?.id;
                return (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => setSelectedTemplateId(template.id)}
                    className={`w-full rounded-xl border p-4 text-left transition-colors shadow-sm ${
                      isActive
                        ? 'border-slate-900 bg-slate-950 text-white'
                        : 'border-border bg-background/95 hover:bg-muted/70'
                    }`}
                  >
                    <div className="text-sm font-semibold">{template.name}</div>
                    <div
                      className={`mt-2 text-xs ${
                        isActive ? 'text-slate-200' : 'text-muted-foreground'
                      }`}
                    >
                      {template.responseWindow}
                    </div>
                  </button>
                );
              })}
            </div>

            {selectedTemplate ? (
              <section className="rounded-2xl border bg-muted/25 p-5 shadow-sm">
                <h2 className="text-lg font-semibold tracking-tight">
                  {selectedTemplate.name}
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  {selectedTemplate.summary}
                </p>

                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Response Window
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedTemplate.responseWindow}
                    </div>
                  </div>
                  <div className="rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Core Owners
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTemplate.owners.map((owner) => (
                        <Badge key={owner} variant="secondary" className="shadow-sm">
                          {owner}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Template Assets
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedTemplate.assets.map((asset) => (
                      <Badge key={asset} variant="outline" className="shadow-sm">
                        {asset}
                      </Badge>
                    ))}
                  </div>
                </div>
              </section>
            ) : null}
          </div>
          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button className="rounded-xl" variant="outline" onClick={() => setTemplateDialogOpen(false)}>
              Close
            </Button>
            <Button className="rounded-xl" onClick={() => setTemplateDialogOpen(false)}>
              Use Template
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={detailDialogOpen}
        onOpenChange={(open) => {
          setDetailDialogOpen(open);
          if (!open) {
            setSelectedAlertDetail(null);
          }
        }}
      >
        <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-3xl sm:rounded-2xl sm:translate-x-[18%]">
          <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
            <DialogTitle>Alert details</DialogTitle>
            <DialogDescription>
              Review the selected alert context without leaving the alerts center.
            </DialogDescription>
          </DialogHeader>

          {selectedAlertDetail ? (
            <div className="grid gap-6 md:grid-cols-[1.2fr_0.8fr]">
              <section className="space-y-4">
                <div className="rounded-2xl border bg-muted/25 p-4 shadow-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold tracking-tight">
                        {selectedAlertDetail.title}
                      </h2>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {selectedAlertDetail.description}
                      </p>
                    </div>
                    <Badge className={`shadow-sm ${getSeverityColor(selectedAlertDetail.severity)}`}>
                      {selectedAlertDetail.severity}
                    </Badge>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <section className="rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Project
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedAlertDetail.project}
                    </div>
                  </section>
                  <section className="rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Type
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedAlertDetail.type}
                    </div>
                  </section>
                </div>
              </section>

              <aside className="rounded-2xl border bg-background/90 p-4 shadow-sm">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Status
                </div>
                <div className="mt-2 text-sm font-medium">
                  Status {selectedAlertDetail.status}
                </div>

                <div className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Severity
                </div>
                <div className="mt-2 text-sm font-medium">
                  Severity {selectedAlertDetail.severity}
                </div>

                <div className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Timeline
                </div>
                <div className="mt-2 text-sm font-medium">
                  {selectedAlertDetail.created_at || selectedAlertDetail.createdAt
                    ? `Created ${formatUtcDate(
                        new Date(
                          selectedAlertDetail.created_at ??
                            selectedAlertDetail.createdAt ??
                            '',
                        ),
                      )}`
                    : 'Created timestamp unavailable'}
                </div>
              </aside>
            </div>
          ) : null}

          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button className="rounded-xl" variant="outline" onClick={() => setDetailDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rulesDialogOpen} onOpenChange={setRulesDialogOpen}>
        <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-3xl sm:rounded-2xl">
          <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
            <DialogTitle>Customize alert rules</DialogTitle>
            <DialogDescription>
              Tune the alert triggers used by the current workspace view.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {draftAlertRules.map((rule, index) => (
              <section key={rule.id} className="rounded-2xl border bg-muted/25 p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">{rule.name}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{rule.description}</p>
                  </div>
                  <Button
                    type="button"
                    variant={rule.enabled ? 'outline' : 'default'}
                    className="rounded-xl bg-background/95 shadow-sm"
                    onClick={() =>
                      setDraftAlertRules((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, enabled: !item.enabled }
                            : item,
                        ),
                      )
                    }
                  >
                    {rule.enabled ? `Disable ${rule.name}` : `Enable ${rule.name}`}
                  </Button>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className="space-y-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                    <label
                      htmlFor={`${rule.id}-threshold`}
                      className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                    >
                      {rule.name} threshold
                    </label>
                    <Input
                      id={`${rule.id}-threshold`}
                      type="number"
                      min={1}
                      className="rounded-xl border-border/80 bg-background/95"
                      value={rule.threshold}
                      onChange={(event) =>
                        setDraftAlertRules((current) =>
                          current.map((item, itemIndex) =>
                            itemIndex === index
                              ? {
                                  ...item,
                                  threshold: Number(event.target.value || item.threshold),
                                }
                              : item,
                          ),
                        )
                      }
                    />
                  </div>

                  <div className="space-y-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Default severity
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(['Critical', 'High', 'Medium'] as const).map((severity) => (
                        <Button
                          key={severity}
                          type="button"
                          size="sm"
                          variant={rule.severity === severity ? 'default' : 'outline'}
                          className="rounded-xl shadow-sm"
                          onClick={() =>
                            setDraftAlertRules((current) =>
                              current.map((item, itemIndex) =>
                                itemIndex === index
                                  ? { ...item, severity }
                                  : item,
                              ),
                            )
                          }
                        >
                          {severity}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              </section>
            ))}
          </div>
          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button className="rounded-xl" variant="outline" onClick={() => setRulesDialogOpen(false)}>
              Cancel
            </Button>
            <Button className="rounded-xl" onClick={saveRules}>Save Rules</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={subscriptionsDialogOpen}
        onOpenChange={setSubscriptionsDialogOpen}
      >
        <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-2xl sm:rounded-2xl">
          <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
            <DialogTitle>Alert subscriptions</DialogTitle>
            <DialogDescription>
              Choose which channels receive alert notifications for this workspace view.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <section className="rounded-2xl border bg-muted/25 p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Email Notifications</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Send alert digests and escalations to an inbox.
                  </p>
                </div>
                <Button
                  type="button"
                  variant={draftAlertSubscriptions.emailEnabled ? 'outline' : 'default'}
                  className="rounded-xl bg-background/95 shadow-sm"
                  onClick={() =>
                    setDraftAlertSubscriptions((current) => ({
                      ...current,
                      emailEnabled: !current.emailEnabled,
                    }))
                  }
                >
                  {draftAlertSubscriptions.emailEnabled
                    ? 'Disable Email Notifications'
                    : 'Enable Email Notifications'}
                </Button>
              </div>

              <div className="mt-4 space-y-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                <label
                  htmlFor="alert-subscription-email"
                  className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  Notification email
                </label>
                <Input
                  id="alert-subscription-email"
                  type="email"
                  className="rounded-xl border-border/80 bg-background/95"
                  value={draftAlertSubscriptions.emailAddress}
                  onChange={(event) =>
                    setDraftAlertSubscriptions((current) => ({
                      ...current,
                      emailAddress: event.target.value,
                    }))
                  }
                  placeholder="alerts@company.com"
                />
              </div>
            </section>

            <section className="rounded-2xl border bg-muted/25 p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-base font-semibold">Slack Notifications</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Post alert updates into an operations channel.
                  </p>
                </div>
                <Button
                  type="button"
                  variant={draftAlertSubscriptions.slackEnabled ? 'outline' : 'default'}
                  className="rounded-xl bg-background/95 shadow-sm"
                  onClick={() =>
                    setDraftAlertSubscriptions((current) => ({
                      ...current,
                      slackEnabled: !current.slackEnabled,
                    }))
                  }
                >
                  {draftAlertSubscriptions.slackEnabled
                    ? 'Disable Slack Notifications'
                    : 'Enable Slack Notifications'}
                </Button>
              </div>

              <div className="mt-4 space-y-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                <label
                  htmlFor="alert-subscription-slack"
                  className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  Slack channel
                </label>
                <Input
                  id="alert-subscription-slack"
                  className="rounded-xl border-border/80 bg-background/95"
                  value={draftAlertSubscriptions.slackChannel}
                  onChange={(event) =>
                    setDraftAlertSubscriptions((current) => ({
                      ...current,
                      slackChannel: event.target.value,
                    }))
                  }
                  placeholder="#project-alerts"
                />
              </div>
            </section>
          </div>

          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button
              className="rounded-xl"
              variant="outline"
              onClick={() => setSubscriptionsDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button className="rounded-xl" onClick={saveSubscriptions}>Save Subscriptions</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={resolveDialogOpen}
        onOpenChange={(open) => {
          setResolveDialogOpen(open);
          if (!open) {
            setSelectedAlert(null);
            setResolutionNotes('');
            setRootCause('');
            setConfirmChecked(false);
          }
        }}
      >
        <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-xl sm:rounded-2xl">
          <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
            <DialogTitle>
              {bulkResolveIds.length > 0 ? 'Bulk resolve alerts' : 'Resolve alert'}
            </DialogTitle>
            <DialogDescription>
              {bulkResolveIds.length > 0
                ? `Apply the shared validation flow to ${bulkResolveIds.length} selected alerts.`
                : selectedAlert
                ? `Complete the required validation to resolve ${selectedAlert.id}.`
                : 'Complete the required validation to resolve this alert.'}
            </DialogDescription>
          </DialogHeader>

          {selectedAlert ? (
            <div className="space-y-4">
              {bulkResolveIds.length > 0 ? (
                <div className="rounded-xl border bg-muted/25 p-4 text-sm shadow-sm">
                  <div className="font-medium">{bulkResolveIds.length} selected alerts</div>
                  <div className="mt-2 text-muted-foreground">
                    Highest severity in selection: {selectedAlert.severity}
                  </div>
                </div>
              ) : null}
              <div className="rounded-xl border bg-muted/25 p-4 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{selectedAlert.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selectedAlert.project} · {selectedAlert.type}
                    </p>
                  </div>
                  <Badge className={`shadow-sm ${getSeverityColor(selectedAlert.severity)}`}>
                    {selectedAlert.severity}
                  </Badge>
                </div>
              </div>

              <div className="space-y-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                <Label htmlFor="resolution-notes">Resolution notes</Label>
                <Textarea
                  id="resolution-notes"
                  value={resolutionNotes}
                  onChange={(event) => setResolutionNotes(event.target.value)}
                  rows={4}
                  placeholder="Document the evidence review and the applied resolution."
                  className="rounded-xl border-border/80 bg-background/95"
                />
                <p className="text-xs text-muted-foreground">
                  {selectedAlert.severity} alerts require at least{' '}
                  {getMinNotesLength(selectedAlert.severity)} characters.
                </p>
                {(selectedAlert.severity === 'Critical' ||
                  selectedAlert.severity === 'High') ? (
                  <p className="text-sm text-amber-700">
                    {selectedAlert.severity} alerts require detailed resolution
                    notes.
                  </p>
                ) : null}
              </div>

              {requiresRootCause(selectedAlert.severity) ? (
                <div className="space-y-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                  <Label htmlFor="root-cause-trigger">Root cause</Label>
                  <Select value={rootCause} onValueChange={setRootCause}>
                    <SelectTrigger
                      id="root-cause-trigger"
                      aria-label="Root cause"
                      className="rounded-xl border-border/80 bg-background/95 shadow-sm"
                    >
                      <SelectValue placeholder="Select root cause category" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="schedule_delay">Schedule Delay</SelectItem>
                      <SelectItem value="resource_constraint">Resource Constraint</SelectItem>
                      <SelectItem value="scope_change">Scope Change</SelectItem>
                      <SelectItem value="external_dependency">External Dependency</SelectItem>
                      <SelectItem value="technical_issue">Technical Issue</SelectItem>
                      <SelectItem value="budget_overrun">Budget Overrun</SelectItem>
                      <SelectItem value="quality_issue">Quality Issue</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              ) : null}

              {requiresCheckbox(selectedAlert.severity) ? (
                <div className="flex items-start gap-2 rounded-xl border bg-background/90 p-4 shadow-sm">
                  <Checkbox
                    id="resolve-alert-confirmation"
                    checked={confirmChecked}
                    onCheckedChange={(checked) => setConfirmChecked(checked === true)}
                  />
                  <Label
                    htmlFor="resolve-alert-confirmation"
                    className="text-sm leading-snug"
                  >
                    I have reviewed the evidence and confirm this alert can be
                    resolved.
                  </Label>
                </div>
              ) : null}
            </div>
          ) : null}

          <DialogFooter className="gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button
              className="rounded-xl"
              variant="outline"
              onClick={() => {
                setResolveDialogOpen(false);
                setSelectedAlert(null);
                setBulkResolveIds([]);
              }}
            >
              Cancel
            </Button>
            <Button
              className="rounded-xl"
              onClick={handleConfirmResolution}
              disabled={
                !selectedAlert ||
                resolutionNotes.trim().length <
                  getMinNotesLength(selectedAlert.severity) ||
                (requiresCheckbox(selectedAlert.severity) && !confirmChecked) ||
                (requiresRootCause(selectedAlert.severity) && !rootCause)
              }
            >
              Confirm Resolution
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
