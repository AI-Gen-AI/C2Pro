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
  FolderKanban,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const mockProjects = [
  {
    id: 'PROJ-001',
    name: 'Petrochemical Plant EPC',
    description: 'Full EPC delivery for greenfield petrochemical facility',
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
    description: 'Equipment upgrades and process optimization',
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
    description: '120km pipeline with 3 compression stations',
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
    description: '500MW utility-scale solar installation',
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
    description: 'Capacity expansion of existing LNG terminal',
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
    description: 'Industrial water treatment and recycling plant',
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

  const filteredProjects = mockProjects.filter((project) => {
    const matchesSearch =
      project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      project.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus =
      statusFilter === 'All Status' || project.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusVariant = (status: string) => {
    switch (status) {
      case 'Active':
        return 'default';
      case 'On Hold':
        return 'secondary';
      case 'Completed':
        return 'success';
      default:
        return 'secondary';
    }
  };

  const getScoreClass = (score: number) => {
    if (score >= 80) return 'score-good';
    if (score >= 60) return 'score-fair';
    return 'score-poor';
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Project
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
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
          <SelectTrigger className="w-[160px]">
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
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-md border bg-card p-4">
          <p className="text-xs font-medium text-muted-foreground">Total Projects</p>
          <p className="mt-1 font-mono text-2xl font-bold">{mockProjects.length}</p>
        </div>
        <div className="rounded-md border bg-card p-4">
          <p className="text-xs font-medium text-muted-foreground">Active</p>
          <p className="mt-1 font-mono text-2xl font-bold text-success">
            {mockProjects.filter((p) => p.status === 'Active').length}
          </p>
        </div>
        <div className="rounded-md border bg-card p-4">
          <p className="text-xs font-medium text-muted-foreground">Total Alerts</p>
          <p className="mt-1 font-mono text-2xl font-bold text-warning">
            {mockProjects.reduce((sum, p) => sum + p.alerts, 0)}
          </p>
        </div>
        <div className="rounded-md border bg-card p-4">
          <p className="text-xs font-medium text-muted-foreground">Critical Issues</p>
          <p className="mt-1 font-mono text-2xl font-bold text-destructive">
            {mockProjects.reduce((sum, p) => sum + p.criticalAlerts, 0)}
          </p>
        </div>
      </div>

      {/* Projects Table */}
      <div className="rounded-md border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Project</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Score</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Alerts</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Budget</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Progress</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">Timeline</th>
                <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredProjects.map((project) => (
                <tr
                  key={project.id}
                  className="transition-colors hover:bg-muted/30"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/projects/${project.id}`}
                      className="group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10">
                          <FolderKanban className="h-4 w-4 text-primary" />
                        </div>
                        <div>
                          <div className="text-sm font-medium group-hover:text-primary">{project.name}</div>
                          <div className="font-mono text-xs text-muted-foreground">{project.id}</div>
                        </div>
                      </div>
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={getStatusVariant(project.status) as "default" | "secondary" | "success"}>
                      {project.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <span className={cn('font-mono text-lg font-bold', getScoreClass(project.coherenceScore))}>
                        {project.coherenceScore}
                      </span>
                      {project.scoreTrend !== 0 && (
                        <div className="flex items-center text-xs">
                          {project.scoreTrend > 0 ? (
                            <TrendingUp className="h-3 w-3 text-success" />
                          ) : (
                            <TrendingDown className="h-3 w-3 text-destructive" />
                          )}
                          <span className={project.scoreTrend > 0 ? 'text-success' : 'text-destructive'}>
                            {Math.abs(project.scoreTrend)}
                          </span>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-3.5 w-3.5 text-warning" />
                      <span className="text-sm font-medium">{project.alerts}</span>
                      {project.criticalAlerts > 0 && (
                        <Badge variant="destructive" className="text-[10px]">
                          {project.criticalAlerts} Critical
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium">{project.budget}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Progress value={project.completion} className="h-1.5 w-16" />
                      <span className="font-mono text-xs">{project.completion}%</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      <span>{project.endDate}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreVertical className="h-4 w-4" />
                      <span className="sr-only">More options</span>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-xs text-muted-foreground">
        Showing {filteredProjects.length} of {mockProjects.length} projects
      </div>
    </div>
  );
}
