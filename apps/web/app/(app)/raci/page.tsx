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
import { Search, Download } from 'lucide-react';
import { useRaci } from '@/hooks/useRaci';
import { useProjects } from '@/hooks/useProjects';

type RaciTemplate = {
  id: string;
  name: string;
  summary: string;
  governanceFocus: string;
  defaultActivities: string[];
  stakeholderTracks: string[];
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

export default function RaciPage() {
  const [projectFilter, setProjectFilter] = useState('all');
  const { data: raciData, loading, error } = useRaci(
    projectFilter === 'all' ? undefined : projectFilter,
  );
  const { data: projects } = useProjects(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState(RACI_TEMPLATES[0]?.id ?? '');

  const selectedTemplate =
    RACI_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    RACI_TEMPLATES[0];

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

  const filteredData = raciData.filter((row) =>
    row.activity.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RACI Matrix</h1>
          <p className="text-muted-foreground">
            Define roles and responsibilities for project activities
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setTemplateDialogOpen(true)}>
            RACI Templates
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
            {(projects ?? []).map((project) => (
              <SelectItem key={project.id} value={project.id}>
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
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

      {/* RACI Matrix Table */}
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
    </div>
  );
}
