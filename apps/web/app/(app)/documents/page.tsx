'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import {
  FileText,
  Upload,
  Search,
  Download,
  Eye,
  MoreVertical,
  FileSpreadsheet,
  File,
  Image as ImageIcon,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FolderOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const mockDocuments = [
  {
    id: 'DOC-001',
    name: 'Contract_Final.pdf',
    type: 'Contract',
    project: 'Petrochemical Plant EPC',
    projectId: 'PROJ-001',
    uploadDate: '2026-01-15',
    size: '2.4 MB',
    pages: 58,
    status: 'Analyzed',
    alertsFound: 7,
    criticalAlerts: 1,
    icon: File,
  },
  {
    id: 'DOC-002',
    name: 'Schedule_v3.xlsx',
    type: 'Schedule',
    project: 'Petrochemical Plant EPC',
    projectId: 'PROJ-001',
    uploadDate: '2026-01-14',
    size: '856 KB',
    pages: 15,
    status: 'Analyzed',
    alertsFound: 4,
    criticalAlerts: 2,
    icon: FileSpreadsheet,
  },
  {
    id: 'DOC-003',
    name: 'Budget_Breakdown_Q1.pdf',
    type: 'Budget',
    project: 'Refinery Modernization',
    projectId: 'PROJ-002',
    uploadDate: '2026-01-13',
    size: '1.8 MB',
    pages: 32,
    status: 'Analyzed',
    alertsFound: 12,
    criticalAlerts: 5,
    icon: File,
  },
  {
    id: 'DOC-004',
    name: 'Technical_Specs_Rev2.pdf',
    type: 'Technical',
    project: 'Solar Farm Installation',
    projectId: 'PROJ-004',
    uploadDate: '2026-01-12',
    size: '5.2 MB',
    pages: 124,
    status: 'Processing',
    alertsFound: 0,
    criticalAlerts: 0,
    icon: File,
  },
  {
    id: 'DOC-005',
    name: 'Site_Photos.zip',
    type: 'Photos',
    project: 'Gas Pipeline Extension',
    projectId: 'PROJ-003',
    uploadDate: '2026-01-10',
    size: '42.3 MB',
    pages: 0,
    status: 'Uploaded',
    alertsFound: 0,
    criticalAlerts: 0,
    icon: ImageIcon,
  },
  {
    id: 'DOC-006',
    name: 'Amendment_No3.pdf',
    type: 'Contract',
    project: 'Water Treatment Facility',
    projectId: 'PROJ-006',
    uploadDate: '2026-01-09',
    size: '1.2 MB',
    pages: 18,
    status: 'Analyzed',
    alertsFound: 3,
    criticalAlerts: 0,
    icon: File,
  },
  {
    id: 'DOC-007',
    name: 'Quality_Report_Dec.pdf',
    type: 'Quality',
    project: 'Refinery Modernization',
    projectId: 'PROJ-002',
    uploadDate: '2026-01-08',
    size: '3.1 MB',
    pages: 45,
    status: 'Analyzed',
    alertsFound: 6,
    criticalAlerts: 1,
    icon: File,
  },
  {
    id: 'DOC-008',
    name: 'Procurement_List.xlsx',
    type: 'Procurement',
    project: 'LNG Terminal Phase 2',
    projectId: 'PROJ-005',
    uploadDate: '2026-01-05',
    size: '642 KB',
    pages: 8,
    status: 'Analyzed',
    alertsFound: 1,
    criticalAlerts: 0,
    icon: FileSpreadsheet,
  },
];

export default function DocumentsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('All Types');
  const [statusFilter, setStatusFilter] = useState('All Status');

  const filteredDocuments = mockDocuments.filter((doc) => {
    const matchesSearch = doc.name
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === 'All Types' || doc.type === typeFilter;
    const matchesStatus =
      statusFilter === 'All Status' || doc.status === statusFilter;
    return matchesSearch && matchesType && matchesStatus;
  });

  // Group documents by project
  const documentsByProject = filteredDocuments.reduce((acc, doc) => {
    if (!acc[doc.projectId]) {
      acc[doc.projectId] = {
        projectId: doc.projectId,
        projectName: doc.project,
        documents: [],
      };
    }
    acc[doc.projectId].documents.push(doc);
    return acc;
  }, {} as Record<string, { projectId: string; projectName: string; documents: typeof mockDocuments }>);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'Analyzed':
        return CheckCircle2;
      case 'Processing':
        return Clock;
      case 'Uploaded':
        return AlertTriangle;
      default:
        return FileText;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Analyzed':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'Processing':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'Uploaded':
        return 'bg-gray-100 text-gray-700 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'Contract':
        return 'bg-blue-100 text-blue-700';
      case 'Schedule':
        return 'bg-orange-100 text-orange-700';
      case 'Budget':
        return 'bg-green-100 text-green-700';
      case 'Technical':
        return 'bg-purple-100 text-purple-700';
      case 'Quality':
        return 'bg-indigo-100 text-indigo-700';
      default:
        return 'bg-gray-100 text-gray-700';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">Documents</h1>
          <p className="text-sm text-muted-foreground">
            All project documents in one place
          </p>
        </div>
        <Button>
          <Upload className="mr-2 h-4 w-4" />
          Upload Document
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select value={typeFilter} onValueChange={setTypeFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Types">All Types</SelectItem>
            <SelectItem value="Contract">Contract</SelectItem>
            <SelectItem value="Schedule">Schedule</SelectItem>
            <SelectItem value="Budget">Budget</SelectItem>
            <SelectItem value="Technical">Technical</SelectItem>
            <SelectItem value="Quality">Quality</SelectItem>
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All Status">All Status</SelectItem>
            <SelectItem value="Analyzed">Analyzed</SelectItem>
            <SelectItem value="Processing">Processing</SelectItem>
            <SelectItem value="Uploaded">Uploaded</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Documents</p>
          <p className="text-2xl font-bold">{mockDocuments.length}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Analyzed</p>
          <p className="text-2xl font-bold text-green-600">
            {mockDocuments.filter((d) => d.status === 'Analyzed').length}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Alerts</p>
          <p className="text-2xl font-bold text-amber-600">
            {mockDocuments.reduce((sum, d) => sum + d.alertsFound, 0)}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Critical Issues</p>
          <p className="text-2xl font-bold text-red-600">
            {mockDocuments.reduce((sum, d) => sum + d.criticalAlerts, 0)}
          </p>
        </div>
      </div>

      {/* Documents Grouped by Project */}
      <div className="space-y-4">
        <Accordion type="multiple" className="space-y-4" defaultValue={Object.keys(documentsByProject)}>
          {Object.values(documentsByProject).map((projectGroup) => (
            <AccordionItem
              key={projectGroup.projectId}
              value={projectGroup.projectId}
              className="rounded-lg border bg-card"
            >
              <AccordionTrigger className="px-4 py-3 hover:no-underline">
                <div className="flex items-center gap-3">
                  <FolderOpen className="h-5 w-5 text-muted-foreground" />
                  <div className="text-left">
                    <div className="font-semibold">{projectGroup.projectName}</div>
                    <div className="text-sm text-muted-foreground">
                      {projectGroup.projectId} • {projectGroup.documents.length} documents
                    </div>
                  </div>
                </div>
              </AccordionTrigger>
              <AccordionContent className="px-0 pb-0">
                <div className="border-t">
                  <table className="w-full">
                    <thead className="border-b bg-muted/30">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                          Document
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                          Type
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                          Status
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                          Alerts
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                          Size
                        </th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-muted-foreground">
                          Date
                        </th>
                        <th className="px-4 py-2"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {projectGroup.documents.map((doc) => {
                        const Icon = doc.icon;
                        const StatusIcon = getStatusIcon(doc.status);
                        return (
                          <tr
                            key={doc.id}
                            className="hover:bg-muted/50 transition-colors"
                          >
                            <td className="px-4 py-3">
                              <Link
                                href={`/projects/${doc.projectId}/evidence/${doc.id}`}
                                className="flex items-center gap-3 hover:underline"
                              >
                                <div className="rounded-lg bg-muted p-2">
                                  <Icon className="h-4 w-4" />
                                </div>
                                <div>
                                  <div className="font-medium text-sm">{doc.name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {doc.id}
                                    {doc.pages > 0 && ` • ${doc.pages} pages`}
                                  </div>
                                </div>
                              </Link>
                            </td>
                            <td className="px-4 py-3">
                              <Badge className={getTypeColor(doc.type)} variant="secondary">
                                {doc.type}
                              </Badge>
                            </td>
                            <td className="px-4 py-3">
                              <Badge
                                variant="outline"
                                className={getStatusColor(doc.status)}
                              >
                                <StatusIcon className="mr-1 h-3 w-3" />
                                {doc.status}
                              </Badge>
                            </td>
                            <td className="px-4 py-3">
                              {doc.alertsFound > 0 ? (
                                <div className="flex items-center gap-2">
                                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                                  <span className="font-medium text-sm">{doc.alertsFound}</span>
                                  {doc.criticalAlerts > 0 && (
                                    <Badge
                                      variant="outline"
                                      className="bg-red-100 text-red-700 border-red-200"
                                    >
                                      {doc.criticalAlerts}
                                    </Badge>
                                  )}
                                </div>
                              ) : (
                                <span className="text-muted-foreground text-sm">-</span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">
                              {doc.size}
                            </td>
                            <td className="px-4 py-3 text-sm text-muted-foreground">
                              {doc.uploadDate}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-1">
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <Eye className="h-4 w-4" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <Download className="h-4 w-4" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                  <MoreVertical className="h-4 w-4" />
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredDocuments.length} documents across {Object.keys(documentsByProject).length} projects
      </div>
    </div>
  );
}
