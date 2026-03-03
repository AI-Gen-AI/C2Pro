"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ArrowLeft,
  FileText,
  AlertTriangle,
  Users,
  Calendar,
  TrendingUp,
  CheckCircle,
  Clock,
  Target,
  BarChart3,
} from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";

function getScoreColor(score: number) {
  if (score >= 80) return "text-green-600";
  if (score >= 60) return "text-yellow-600";
  return "text-red-600";
}

function getScoreBg(score: number) {
  if (score >= 80) return "bg-green-100";
  if (score >= 60) return "bg-yellow-100";
  return "bg-red-100";
}

export default function DemoProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const project = SAMPLE_DATA.projects.find((p) => p.id === projectId);
  const projectAlerts = SAMPLE_DATA.alerts.filter(
    (a) => a.project_id === projectId
  );
  const documents = SAMPLE_DATA.documents;
  const stakeholders = SAMPLE_DATA.stakeholders;
  const clauses = SAMPLE_DATA.clauses;

  if (!project) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center space-y-4">
          <h2 className="text-xl font-bold">Project Not Found</h2>
          <p className="text-muted-foreground">
            The requested demo project could not be found.
          </p>
          <Button onClick={() => router.push("/demo/projects")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Projects
          </Button>
        </div>
      </div>
    );
  }

  const openAlerts = projectAlerts.filter((a) => a.status === "open");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push("/demo/projects")}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{project.name}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {project.description}
            </p>
            <div className="flex items-center gap-2 mt-2">
              <Badge
                className={
                  project.status === "active"
                    ? "bg-green-100 text-green-700"
                    : project.status === "draft"
                    ? "bg-gray-100 text-gray-700"
                    : "bg-blue-100 text-blue-700"
                }
              >
                {project.status}
              </Badge>
              <span className="text-xs text-muted-foreground">
                Created {new Date(project.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Viewing demo project details. Sign in to manage your own projects and
          documents.
        </p>
      </div>

      {/* Coherence Score Card */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div
              className={`flex items-center justify-center w-20 h-20 rounded-xl font-bold text-3xl ${getScoreBg(
                project.coherence_score
              )} ${getScoreColor(project.coherence_score)}`}
            >
              {project.coherence_score}
            </div>
            <div>
              <h2 className="text-lg font-semibold">Coherence Score</h2>
              <p className="text-sm text-muted-foreground">
                Overall contract alignment metric
              </p>
              <div className="flex items-center gap-1 mt-2 text-sm text-green-600">
                <TrendingUp className="w-4 h-4" />
                <span>+3 points this week</span>
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-4">
              <div className="text-center">
                <BarChart3 className="w-5 h-5 mx-auto text-muted-foreground" />
                <p className="text-xs text-muted-foreground mt-1">Trend</p>
              </div>
              <div className="text-center">
                <Target className="w-5 h-5 mx-auto text-muted-foreground" />
                <p className="text-xs text-muted-foreground mt-1">Target: 90</p>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-100">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{project.document_count}</p>
              <p className="text-xs text-muted-foreground">Documents</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-100">
              <Calendar className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{project.clause_count}</p>
              <p className="text-xs text-muted-foreground">Clauses</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-orange-100">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{openAlerts.length}</p>
              <p className="text-xs text-muted-foreground">Open Alerts</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-green-100">
              <Users className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold">{project.stakeholder_count}</p>
              <p className="text-xs text-muted-foreground">Stakeholders</p>
            </div>
          </div>
        </Card>
      </div>

      {/* Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Project Alerts */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Project Alerts</h3>
            <Link href="/demo/alerts">
              <Button variant="ghost" size="sm">
                View All
              </Button>
            </Link>
          </div>
          <div className="space-y-3">
            {projectAlerts.length > 0 ? (
              projectAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className={`p-3 rounded-lg border ${
                    alert.severity === "critical"
                      ? "bg-red-50 border-red-200"
                      : alert.severity === "high"
                      ? "bg-orange-50 border-orange-200"
                      : "bg-yellow-50 border-yellow-200"
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <AlertTriangle
                      className={`w-4 h-4 mt-0.5 ${
                        alert.severity === "critical"
                          ? "text-red-600"
                          : alert.severity === "high"
                          ? "text-orange-600"
                          : "text-yellow-600"
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium line-clamp-2">
                        {alert.message}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge
                          className={
                            alert.severity === "critical"
                              ? "bg-red-100 text-red-700"
                              : alert.severity === "high"
                              ? "bg-orange-100 text-orange-700"
                              : "bg-yellow-100 text-yellow-700"
                          }
                        >
                          {alert.severity}
                        </Badge>
                        {alert.status === "open" ? (
                          <span className="flex items-center gap-1 text-xs text-muted-foreground">
                            <Clock className="w-3 h-3" /> Open
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-green-600">
                            <CheckCircle className="w-3 h-3" /> Resolved
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No alerts for this project
              </p>
            )}
          </div>
        </Card>

        {/* Sample Documents */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Documents</h3>
            <Link href="/demo/documents">
              <Button variant="ghost" size="sm">
                View All
              </Button>
            </Link>
          </div>
          <div className="space-y-3">
            {documents.slice(0, 3).map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg"
              >
                <FileText className="w-5 h-5 text-blue-600" />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{doc.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {doc.clause_count} clauses extracted
                  </p>
                </div>
                <Badge variant="outline">{doc.type}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Sample Clauses */}
      <Card className="p-4">
        <h3 className="font-semibold mb-4">Sample Extracted Clauses</h3>
        <div className="space-y-3">
          {clauses.slice(0, 3).map((clause) => (
            <div
              key={clause.id}
              className="p-3 bg-slate-50 rounded-lg border border-slate-200"
            >
              <div className="flex items-center gap-2 mb-2">
                <Badge variant="outline">
                  {clause.type.replace(/_/g, " ")}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {Math.round(clause.confidence * 100)}% confidence
                </span>
              </div>
              <p className="text-sm text-foreground">{clause.text}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
