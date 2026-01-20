'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Search,
  Plus,
  MoreVertical,
  Calendar,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const mockProjects = [
  {
    id: 'PROJ-001',
    name: 'Petrochemical Plant EPC',
    description: 'Engineering, Procurement, and Construction project for new petrochemical facility',
    status: 'Active',
    coherenceScore: 78,
    scoreTrend: -3,
    alerts: 7,
    criticalAlerts: 3,
    budget: '$450M',
    completion: 45,
    startDate: '2025-01-15',
    endDate: '2026-12-31',
  },
  {
    id: 'PROJ-002',
    name: 'Refinery Modernization',
    description: 'Upgrade and modernization of existing refinery infrastructure',
    status: 'Active',
    coherenceScore: 64,
    scoreTrend: 2,
    alerts: 12,
    criticalAlerts: 5,
    budget: '$280M',
    completion: 62,
    startDate: '2024-08-01',
    endDate: '2026-06-30',
  },
  {
    id: 'PROJ-003',
    name: 'Gas Pipeline Extension',
    description: 'Extension of natural gas pipeline network across three regions',
    status: 'On Hold',
    coherenceScore: 92,
    scoreTrend: 0,
    alerts: 2,
    criticalAlerts: 0,
    budget: '$185M',
    completion: 28,
    startDate: '2025-03-01',
    endDate: '2027-02-28',
  },
  {
    id: 'PROJ-004',
    name: 'Solar Farm Installation',
    description: '500MW solar power generation facility with battery storage',
    status: 'Active',
    coherenceScore: 85,
    scoreTrend: 5,
    alerts: 4,
    criticalAlerts: 1,
    budget: '$320M',
    completion: 35,
    startDate: '2025-02-10',
    endDate: '2026-11-30',
  },
  {
    id: 'PROJ-005',
    name: 'LNG Terminal Phase 2',
    description: 'Expansion of liquefied natural gas import/export terminal',
    status: 'Completed',
    coherenceScore: 94,
    scoreTrend: 1,
    alerts: 1,
    criticalAlerts: 0,
    budget: '$590M',
    completion: 100,
    startDate: '2023-06-01',
    endDate: '2025-12-15',
  },
  {
    id: 'PROJ-006',
    name: 'Water Treatment Facility',
    description: 'Industrial wastewater treatment and recycling plant',
    status: 'Active',
    coherenceScore: 71,
    scoreTrend: -2,
    alerts: 8,
    criticalAlerts: 2,
    budget: '$95M',
    completion: 58,
    startDate: '2024-11-01',
    endDate: '2026-08-31',
  },
];

export default function ProjectsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('All Status');
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table');

  const filteredProjects = mockProjects.filter((project) => {
    const matchesSearch =
      project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      project.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'All Status' || project.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Active':
        return 'bg-slate-900 text-white';
      case 'On Hold':
        return 'bg-gray-100 text-gray-700';
      case 'Completed':
        return 'bg-blue-100 text-blue-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Projects</h1>
          <p className="text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Status">All Status</SelectItem>
            <SelectItem value="Active">Active</SelectItem>
            <SelectItem value="On Hold">On Hold</SelectItem>
            <SelectItem value="Completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Projects</p>
          <p className="text-2xl font-bold">{mockProjects.length}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Active</p>
          <p className="text-2xl font-bold text-green-600">
            {mockProjects.filter((p) => p.status === 'Active').length}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Alerts</p>
          <p className="text-2xl font-bold text-amber-600">
            {mockProjects.reduce((sum, p) => sum + p.alerts, 0)}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Critical Issues</p>
          <p className="text-2xl font-bold text-red-600">
            {mockProjects.reduce((sum, p) => sum + p.criticalAlerts, 0)}
          </p>
        </div>
      </div>

      {/* Projects Table */}
      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Project
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Score
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Alerts
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Budget
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Progress
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Timeline
                </th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredProjects.map((project) => (
                <tr
                  key={project.id}
                  className="hover:bg-muted/50 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/projects/${project.id}`}
                      className="hover:underline"
                    >
                      <div className="font-medium">{project.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {project.id}
                      </div>
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Badge className={getStatusColor(project.status)}>
                      {project.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={cn(
                          'text-xl font-bold',
                          getScoreColor(project.coherenceScore)
                        )}
                      >
                        {project.coherenceScore}
                      </span>
                      {project.scoreTrend !== 0 && (
                        <div className="flex items-center text-xs">
                          {project.scoreTrend > 0 ? (
                            <TrendingUp className="h-3 w-3 text-green-600" />
                          ) : (
                            <TrendingDown className="h-3 w-3 text-red-600" />
                          )}
                          <span
                            className={
                              project.scoreTrend > 0
                                ? 'text-green-600'
                                : 'text-red-600'
                            }
                          >
                            {Math.abs(project.scoreTrend)}
                          </span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-amber-600" />
                      <span className="font-medium">{project.alerts}</span>
                      {project.criticalAlerts > 0 && (
                        <Badge
                          variant="outline"
                          className="bg-red-100 text-red-700 border-red-200"
                        >
                          {project.criticalAlerts} Critical
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium">{project.budget}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Progress value={project.completion} className="w-20" />
                      <span className="text-sm font-medium">
                        {project.completion}%
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      <span>{project.endDate}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Button variant="ghost" size="icon">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredProjects.length} of {mockProjects.length} projects
      </div>
    </div>
  );
}
