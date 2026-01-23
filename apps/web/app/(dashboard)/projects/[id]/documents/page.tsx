'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
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
  ArrowLeft,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Mock data - in real app this would come from API
const mockDocuments: Record<string, any[]> = {
  'PROJ-001': [
    {
      id: 'DOC-001',
      name: 'Contract_Final.pdf',
      type: 'Contract',
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
      uploadDate: '2026-01-14',
      size: '856 KB',
      pages: 15,
      status: 'Analyzed',
      alertsFound: 4,
      criticalAlerts: 2,
      icon: FileSpreadsheet,
    },
  ],
  'PROJ-002': [
    {
      id: 'DOC-003',
      name: 'Budget_Breakdown_Q1.pdf',
      type: 'Budget',
      uploadDate: '2026-01-13',
      size: '1.8 MB',
      pages: 32,
      status: 'Analyzed',
      alertsFound: 12,
      criticalAlerts: 5,
      icon: File,
    },
  ],
};

const projectNames: Record<string, string> = {
  'PROJ-001': 'Petrochemical Plant EPC',
  'PROJ-002': 'Refinery Modernization',
};

export default function ProjectDocumentsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('All Types');
  const [statusFilter, setStatusFilter] = useState('All Status');

  const projectDocs = mockDocuments[projectId] || [];
  const projectName = projectNames[projectId] || 'Unknown Project';

  const filteredDocuments = projectDocs.filter((doc) => {
    const matchesSearch = doc.name
      .toLowerCase()
      .includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === 'All Types' || doc.type === typeFilter;
    const matchesStatus =
      statusFilter === 'All Status' || doc.status === statusFilter;
    return matchesSearch && matchesType && matchesStatus;
  });

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
        <div className="space-y-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push(`/projects/${projectId}`)}
            className="mb-2"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Project
          </Button>
          <h1 className="text-3xl font-bold tracking-tight">Documents</h1>
          <p className="text-muted-foreground">
            {projectName} • {projectId}
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
          <p className="text-2xl font-bold">{projectDocs.length}</p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Analyzed</p>
          <p className="text-2xl font-bold text-green-600">
            {projectDocs.filter((d) => d.status === 'Analyzed').length}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Total Alerts</p>
          <p className="text-2xl font-bold text-amber-600">
            {projectDocs.reduce((sum, d) => sum + d.alertsFound, 0)}
          </p>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <p className="text-sm text-muted-foreground">Critical Issues</p>
          <p className="text-2xl font-bold text-red-600">
            {projectDocs.reduce((sum, d) => sum + d.criticalAlerts, 0)}
          </p>
        </div>
      </div>

      {/* Documents Table */}
      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Document
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Status
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Alerts
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Size
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium">
                  Upload Date
                </th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {filteredDocuments.length > 0 ? (
                filteredDocuments.map((doc) => {
                  const Icon = doc.icon;
                  const StatusIcon = getStatusIcon(doc.status);
                  return (
                    <tr
                      key={doc.id}
                      className="hover:bg-muted/50 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <Link
                          href={`/projects/${projectId}/evidence/${doc.id}`}
                          className="flex items-center gap-3 hover:underline"
                        >
                          <div className="rounded-lg bg-muted p-2">
                            <Icon className="h-5 w-5" />
                          </div>
                          <div>
                            <div className="font-medium">{doc.name}</div>
                            <div className="text-sm text-muted-foreground">
                              {doc.id}
                              {doc.pages > 0 && ` • ${doc.pages} pages`}
                            </div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <Badge className={getTypeColor(doc.type)}>
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
                            <span className="font-medium">{doc.alertsFound}</span>
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
                          <span className="text-muted-foreground">-</span>
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
                          <Button variant="ghost" size="icon">
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon">
                            <Download className="h-4 w-4" />
                          </Button>
                          <Button variant="ghost" size="icon">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No documents found for this project
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="text-sm text-muted-foreground">
        Showing {filteredDocuments.length} of {projectDocs.length} documents
      </div>
    </div>
  );
}
