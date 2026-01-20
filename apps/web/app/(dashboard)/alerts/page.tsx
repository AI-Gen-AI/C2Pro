'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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

const mockAlerts = [
  {
    id: 'AL-001',
    severity: 'Critical',
    type: 'Legal',
    title: 'Contract Penalty Clause Violation Risk',
    description: 'Clause 4.2.1 specifies 30-day delay penalty. Current trajectory shows 45-day delay.',
    project: 'Petrochemical Plant EPC',
    status: 'Open',
  },
  {
    id: 'AL-002',
    severity: 'Critical',
    type: 'Financial',
    title: 'Budget Overrun Threshold Exceeded',
    description: 'Equipment procurement costs 25% above baseline estimates.',
    project: 'Petrochemical Plant EPC',
    status: 'Open',
  },
  {
    id: 'AL-003',
    severity: 'Critical',
    type: 'Technical',
    title: 'Equipment Compatibility Issue',
    description: 'New compressor specifications conflict with existing infrastructure.',
    project: 'Refinery Modernization',
    status: 'In Progress',
  },
  {
    id: 'AL-004',
    severity: 'High',
    type: 'Schedule',
    title: 'Critical Path Delay - Foundation Work',
    description: 'Foundation completion delayed by 12 days due to ground conditions.',
    project: 'Petrochemical Plant EPC',
    status: 'Open',
  },
  {
    id: 'AL-005',
    severity: 'High',
    type: 'Scope',
    title: 'Grid Connection Requirements Changed',
    description: 'Utility company issued new interconnection requirements.',
    project: 'Solar Farm Installation',
    status: 'Open',
  },
  {
    id: 'AL-006',
    severity: 'Medium',
    type: 'Financial',
    title: 'Material Cost Variance',
    description: 'Steel prices increased 8% above budgeted rates.',
    project: 'Refinery Modernization',
    status: 'Open',
  },
  {
    id: 'AL-007',
    severity: 'Medium',
    type: 'Legal',
    title: 'Permit Renewal Pending',
    description: 'Environmental permit expires in 45 days. Renewal application in progress.',
    project: 'Water Treatment Facility',
    status: 'In Progress',
  },
];

export default function AlertsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState('All Severity');
  const [statusFilter, setStatusFilter] = useState('All Status');

  const filteredAlerts = mockAlerts.filter((alert) => {
    const matchesSearch =
      alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      alert.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSeverity =
      severityFilter === 'All Severity' || alert.severity === severityFilter;
    const matchesStatus =
      statusFilter === 'All Status' || alert.status === statusFilter;
    return matchesSearch && matchesSeverity && matchesStatus;
  });

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
          <h1 className="text-3xl font-bold tracking-tight">Alerts Center</h1>
          <p className="text-muted-foreground">
            Monitor and manage all project alerts
          </p>
        </div>
        <Button>
          + New Alert
        </Button>
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
    </div>
  );
}
