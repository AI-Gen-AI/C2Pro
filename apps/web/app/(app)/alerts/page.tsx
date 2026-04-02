'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  bulkResolveAlerts,
  getAlertWorkspaceSettings,
  saveAlertWorkspaceSettings,
} from '@/lib/api';
import { Button } from '@/components/ui/button';
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
      alert.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity =
      severityFilter === 'All Severity' || alert.severity === severityFilter;
    const matchesStatus =
      statusFilter === 'All Status' || alert.status === statusFilter;
    return matchesSearch && matchesSeverity && matchesStatus;
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
      tone: "border-red-200 bg-red-50/70 text-red-900",
    },
    {
      title: "Open Alerts",
      value: `${openCount} currently require action`,
      detail: "Includes open and in-progress remediation work.",
      tone: "border-slate-200 bg-slate-50 text-slate-900",
    },
    {
      title: "Top Impacted Project",
      value: topProjectEntry?.[0] ?? "No alerts in scope",
      detail: topProjectEntry
        ? `${topProjectEntry[1]} alerts in current scope`
        : "Adjust filters to inspect alert concentrations.",
      tone: "border-amber-200 bg-amber-50/70 text-amber-950",
    },
    {
      title: "SLA Violations",
      value: `${overdueCount} overdue`,
      detail: overdueCount
        ? "Alerts that have exceeded the current severity response window."
        : "No active SLA violations in the current workspace scope.",
      tone: "border-rose-200 bg-rose-50/70 text-rose-950",
    },
  ];

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'Critical':
        return 'bg-red-100 text-red-700 border-red-200';
      case 'High':
        return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'Medium':
        return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Open':
        return 'bg-slate-900 text-white';
      case 'In Progress':
        return 'bg-blue-100 text-blue-700';
      case 'Resolved':
        return 'bg-green-100 text-green-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Alerts Center</h1>
          <p className="text-sm text-muted-foreground">
            Monitor and manage all project alerts
          </p>
          <p className="mt-2 text-sm font-medium text-foreground">
            {activeRuleCount} active rules
          </p>
          <p className="text-sm text-muted-foreground">
            {activeSubscriptionCount > 0
              ? `${activeSubscriptionCount} active subscriptions`
              : 'No active subscriptions'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={openSubscriptionsDialog}>
            Subscriptions
          </Button>
          <Button variant="outline" onClick={openRulesDialog}>
            Alert Rules
          </Button>
          <Button variant="outline" onClick={() => setTemplateDialogOpen(true)}>
            Alert Templates
          </Button>
          <Button>
            + New Alert
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {analyticsCards.map((card) => (
          <section
            key={card.title}
            className={`rounded-lg border p-4 shadow-sm ${card.tone}`}
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
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search alerts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={severityFilter} onValueChange={setSeverityFilter}>
          <SelectTrigger className="w-[180px]">
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
          <SelectTrigger className="w-[180px]">
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

      {selectedAlertIds.length > 0 ? (
        <section className="flex items-center justify-between rounded-lg border bg-muted/30 px-4 py-3">
          <div className="text-sm font-medium">
            {selectedAlertIds.length} alerts selected
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setSelectedAlertIds([])}>
              Clear Selection
            </Button>
            <Button onClick={openBulkResolveDialog}>Bulk Resolve</Button>
          </div>
        </section>
      ) : null}

      {/* Alerts Table */}
      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="w-12 p-4">
                  <Checkbox aria-label="Select all alerts" />
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">ID</th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Severity
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">Type</th>
                <th className="px-4 py-3 text-left text-sm font-medium">Title</th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Project
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  SLA
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredAlerts.map(({ alert, sla }) => (
                <tr
                  key={alert.id}
                  className="hover:bg-muted/50 transition-colors"
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
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {alert.id}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant="outline"
                      className={getSeverityColor(alert.severity)}
                    >
                      {alert.severity}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-sm">{alert.type}</td>
                  <td className="px-4 py-3">
                    <div className="max-w-md">
                      <div className="font-medium">{alert.title}</div>
                      <div className="text-sm text-muted-foreground">
                        {alert.description}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm">{alert.project}</td>
                  <td className="px-4 py-3">
                    <Badge className={getStatusColor(alert.status)}>
                      {alert.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="space-y-1">
                      <Badge className={sla.tone}>{sla.statusLabel}</Badge>
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
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`View alert ${alert.id}`}
                        onClick={() => openDetailDialog(alert as AlertRecord)}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
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
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Alert Templates</DialogTitle>
            <DialogDescription>
              Start from an alert response template
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-[1.1fr_1.4fr]">
            <div className="space-y-2">
              {ALERT_TEMPLATES.map((template) => {
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
                      {template.responseWindow}
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
                      Response Window
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedTemplate.responseWindow}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Core Owners
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTemplate.owners.map((owner) => (
                        <Badge key={owner} variant="secondary">
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
                      <Badge key={asset} variant="outline">
                        {asset}
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
        open={detailDialogOpen}
        onOpenChange={(open) => {
          setDetailDialogOpen(open);
          if (!open) {
            setSelectedAlertDetail(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-3xl sm:translate-x-[18%]">
          <DialogHeader>
            <DialogTitle>Alert details</DialogTitle>
            <DialogDescription>
              Review the selected alert context without leaving the alerts center.
            </DialogDescription>
          </DialogHeader>

          {selectedAlertDetail ? (
            <div className="grid gap-6 md:grid-cols-[1.2fr_0.8fr]">
              <section className="space-y-4">
                <div className="rounded-xl border bg-muted/20 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold tracking-tight">
                        {selectedAlertDetail.title}
                      </h2>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {selectedAlertDetail.description}
                      </p>
                    </div>
                    <Badge className={getSeverityColor(selectedAlertDetail.severity)}>
                      {selectedAlertDetail.severity}
                    </Badge>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <section className="rounded-lg border p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Project
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedAlertDetail.project}
                    </div>
                  </section>
                  <section className="rounded-lg border p-4">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Type
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {selectedAlertDetail.type}
                    </div>
                  </section>
                </div>
              </section>

              <aside className="rounded-xl border bg-background p-4">
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

          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={rulesDialogOpen} onOpenChange={setRulesDialogOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Customize alert rules</DialogTitle>
            <DialogDescription>
              Tune the alert triggers used by the current workspace view.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {draftAlertRules.map((rule, index) => (
              <section key={rule.id} className="rounded-xl border bg-muted/20 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-semibold">{rule.name}</h2>
                    <p className="mt-1 text-sm text-muted-foreground">{rule.description}</p>
                  </div>
                  <Button
                    type="button"
                    variant={rule.enabled ? 'outline' : 'default'}
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
                  <div className="space-y-2">
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

                  <div className="space-y-2">
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
          <DialogFooter>
            <Button variant="outline" onClick={() => setRulesDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={saveRules}>Save Rules</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={subscriptionsDialogOpen}
        onOpenChange={setSubscriptionsDialogOpen}
      >
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Alert subscriptions</DialogTitle>
            <DialogDescription>
              Choose which channels receive alert notifications for this workspace view.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <section className="rounded-xl border bg-muted/20 p-4">
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

              <div className="mt-4 space-y-2">
                <label
                  htmlFor="alert-subscription-email"
                  className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  Notification email
                </label>
                <Input
                  id="alert-subscription-email"
                  type="email"
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

            <section className="rounded-xl border bg-muted/20 p-4">
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

              <div className="mt-4 space-y-2">
                <label
                  htmlFor="alert-subscription-slack"
                  className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  Slack channel
                </label>
                <Input
                  id="alert-subscription-slack"
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

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSubscriptionsDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button onClick={saveSubscriptions}>Save Subscriptions</Button>
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
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
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
                <div className="rounded-lg border bg-muted/20 p-4 text-sm">
                  <div className="font-medium">{bulkResolveIds.length} selected alerts</div>
                  <div className="mt-2 text-muted-foreground">
                    Highest severity in selection: {selectedAlert.severity}
                  </div>
                </div>
              ) : null}
              <div className="rounded-lg border bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="font-medium">{selectedAlert.title}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {selectedAlert.project} · {selectedAlert.type}
                    </p>
                  </div>
                  <Badge className={getSeverityColor(selectedAlert.severity)}>
                    {selectedAlert.severity}
                  </Badge>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="resolution-notes">Resolution notes</Label>
                <Textarea
                  id="resolution-notes"
                  value={resolutionNotes}
                  onChange={(event) => setResolutionNotes(event.target.value)}
                  rows={4}
                  placeholder="Document the evidence review and the applied resolution."
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
                <div className="space-y-2">
                  <Label htmlFor="root-cause-trigger">Root cause</Label>
                  <Select value={rootCause} onValueChange={setRootCause}>
                    <SelectTrigger
                      id="root-cause-trigger"
                      aria-label="Root cause"
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
                <div className="flex items-start gap-2">
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

          <DialogFooter>
            <Button
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
