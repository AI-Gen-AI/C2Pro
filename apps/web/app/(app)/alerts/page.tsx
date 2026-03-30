'use client';

import { useState } from 'react';
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

export default function AlertsPage() {
  const { alerts, loading, error } = useAlerts();
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('All Severity');
  const [statusFilter, setStatusFilter] = useState('All Status');
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState(ALERT_TEMPLATES[0]?.id ?? '');

  const selectedTemplate =
    ALERT_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    ALERT_TEMPLATES[0];

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

  const filteredAlerts = alerts.filter((alert) => {
    const matchesSearch =
      alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity =
      severityFilter === 'All Severity' || alert.severity === severityFilter;
    const matchesStatus =
      statusFilter === 'All Status' || alert.status === statusFilter;
    return matchesSearch && matchesSeverity && matchesStatus;
  });
  const severityCounts = alerts.reduce<Record<string, number>>((acc, alert) => {
    acc[alert.severity] = (acc[alert.severity] ?? 0) + 1;
    return acc;
  }, {});
  const statusCounts = alerts.reduce<Record<string, number>>((acc, alert) => {
    acc[alert.status] = (acc[alert.status] ?? 0) + 1;
    return acc;
  }, {});
  const topProjectEntry = Object.entries(
    filteredAlerts.reduce<Record<string, number>>((acc, alert) => {
      acc[alert.project] = (acc[alert.project] ?? 0) + 1;
      return acc;
    }, {}),
  ).sort(([, a], [, b]) => b - a)[0];
  const openCount =
    (statusCounts["Open"] ?? 0) + (statusCounts["In Progress"] ?? 0);
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
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setTemplateDialogOpen(true)}>
            Alert Templates
          </Button>
          <Button>
            + New Alert
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
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

      {/* Alerts Table */}
      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="w-12 p-4">
                  <Checkbox />
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
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredAlerts.map((alert) => (
                <tr
                  key={alert.id}
                  className="hover:bg-muted/50 transition-colors"
                >
                  <td className="p-4">
                    <Checkbox />
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
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon">
                        <Eye className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon">
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
    </div>
  );
}
