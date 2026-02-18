"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FolderKanban,
  FileText,
  AlertTriangle,
  Users,
  TrendingUp,
  TrendingDown,
  ArrowRight,
  CheckCircle,
  Clock,
  Target,
  DollarSign,
  Upload,
  UserPlus,
} from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";

// Circular progress component for coherence score
function CoherenceGauge({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;
  const getColor = (s: number) => {
    if (s >= 80) return "#22c55e";
    if (s >= 60) return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="relative w-32 h-32">
      <svg className="w-32 h-32 transform -rotate-90">
        <circle
          cx="64"
          cy="64"
          r="45"
          stroke="#e5e7eb"
          strokeWidth="10"
          fill="none"
        />
        <circle
          cx="64"
          cy="64"
          r="45"
          stroke={getColor(score)}
          strokeWidth="10"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-1000"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold" style={{ color: getColor(score) }}>
          {score}
        </span>
        <span className="text-xs text-muted-foreground">/ 100</span>
      </div>
    </div>
  );
}

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

// Sample recent activity data
const recentActivity = [
  {
    id: 1,
    type: "alert",
    icon: AlertTriangle,
    iconColor: "text-red-500",
    iconBg: "bg-red-100",
    message: "Critical alert raised: Contract Penalty Clause Violation Risk",
    time: "5 days ago",
  },
  {
    id: 2,
    type: "document",
    icon: FileText,
    iconColor: "text-blue-500",
    iconBg: "bg-blue-100",
    message: "Contract amendment v3 uploaded for review",
    time: "5 days ago",
  },
  {
    id: 3,
    type: "score",
    icon: TrendingUp,
    iconColor: "text-green-500",
    iconBg: "bg-green-100",
    message: "Coherence score increased from 76 to 78",
    time: "6 days ago",
  },
  {
    id: 4,
    type: "resolved",
    icon: CheckCircle,
    iconColor: "text-green-500",
    iconBg: "bg-green-100",
    message: "Alert resolved: Weather Delay - Minor",
    time: "10 days ago",
  },
  {
    id: 5,
    type: "stakeholder",
    icon: UserPlus,
    iconColor: "text-purple-500",
    iconBg: "bg-purple-100",
    message: "New stakeholder added: Lisa Brown (QA Manager)",
    time: "11 days ago",
  },
];

export default function DemoDashboardPage() {
  const projects = SAMPLE_DATA.projects;
  const alerts = SAMPLE_DATA.alerts;
  const documents = SAMPLE_DATA.documents;
  const stakeholders = SAMPLE_DATA.stakeholders;
  const clauses = SAMPLE_DATA.clauses;

  // Calculate stats
  const openAlerts = alerts.filter((a) => a.status === "open");
  const criticalAlerts = alerts.filter((a) => a.severity === "critical" && a.status === "open");
  const avgCoherence = Math.round(
    projects.reduce((sum, p) => sum + p.coherence_score, 0) / projects.length
  );
  const totalDocuments = documents.length;
  const totalClauses = clauses.length;
  const activeProjects = projects.filter((p) => p.status === "active").length;
  const projectsAtRisk = projects.filter((p) => p.coherence_score < 80).length;
  const budgetHealth = 62; // Demo value
  const pendingReview = 12; // Demo value

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Contract coherence overview and key metrics
        </p>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Welcome to the C2Pro demo. Explore sample project data to see how contract coherence analysis works. Sign in to analyze your own documents.
        </p>
      </div>

      {/* Key Metrics - Matching original design */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        {/* Coherence Score with Gauge */}
        <Card className="p-4">
          <p className="text-sm font-medium text-muted-foreground mb-2">
            Coherence Score
          </p>
          <div className="flex justify-center">
            <CoherenceGauge score={avgCoherence} />
          </div>
          <div className="flex items-center justify-center gap-1 mt-2 text-sm text-green-600">
            <TrendingUp className="w-4 h-4" />
            <span>+2 vs last week</span>
          </div>
        </Card>

        {/* Active Projects */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Active Projects
            </p>
            <FolderKanban className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-3xl font-bold text-foreground">{activeProjects * 4}</p>
          <Badge className="mt-2 bg-orange-100 text-orange-700">
            {projectsAtRisk} at risk
          </Badge>
        </Card>

        {/* Open Alerts */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Open Alerts
            </p>
            <AlertTriangle className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-3xl font-bold text-foreground">{openAlerts.length + 3}</p>
          <Badge className="mt-2 bg-red-100 text-red-700">
            {criticalAlerts.length + 2} critical
          </Badge>
        </Card>

        {/* Budget Health */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Budget Health
            </p>
            <DollarSign className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-3xl font-bold text-foreground">{budgetHealth}%</p>
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Used</span>
              <span>{budgetHealth}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${budgetHealth}%` }}
              />
            </div>
          </div>
        </Card>

        {/* Documents Processed */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-muted-foreground">
              Documents Processed
            </p>
            <FileText className="w-4 h-4 text-muted-foreground" />
          </div>
          <p className="text-3xl font-bold text-foreground">156</p>
          <Badge className="mt-2 bg-cyan-100 text-cyan-700 border border-cyan-200">
            {pendingReview} pending review
          </Badge>
        </Card>
      </div>

      {/* Recent Activity */}
      <Card className="p-4">
        <h2 className="font-semibold text-foreground mb-4">Recent Activity</h2>
        <div className="space-y-4">
          {recentActivity.map((activity) => {
            const Icon = activity.icon;
            return (
              <div key={activity.id} className="flex items-start gap-3">
                <div className={`p-2 rounded-full ${activity.iconBg}`}>
                  <Icon className={`w-4 h-4 ${activity.iconColor}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-foreground">{activity.message}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {activity.time}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Projects Overview */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-foreground">Projects</h2>
            <Link href="/demo/projects">
              <Button variant="ghost" size="sm">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>
          <div className="space-y-3">
            {projects.map((project) => (
              <div
                key={project.id}
                className="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{project.name}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge
                      variant="outline"
                      className={
                        project.status === "active"
                          ? "border-green-300 text-green-700"
                          : "border-gray-300 text-gray-700"
                      }
                    >
                      {project.status}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {project.document_count} docs
                    </span>
                  </div>
                </div>
                <div
                  className={`flex items-center justify-center w-12 h-12 rounded-lg font-bold ${getScoreBg(
                    project.coherence_score
                  )} ${getScoreColor(project.coherence_score)}`}
                >
                  {project.coherence_score}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Recent Alerts */}
        <Card className="p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-foreground">Recent Alerts</h2>
            <Link href="/demo/alerts">
              <Button variant="ghost" size="sm">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </Link>
          </div>
          <div className="space-y-3">
            {alerts.slice(0, 4).map((alert) => (
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
                    <p className="text-sm font-medium line-clamp-1">
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
                        <Clock className="w-3 h-3 text-muted-foreground" />
                      ) : (
                        <CheckCircle className="w-3 h-3 text-green-600" />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Quick Links */}
      <div className="grid gap-4 md:grid-cols-4">
        <Link href="/demo/projects">
          <Card className="p-4 hover:shadow-md transition-shadow cursor-pointer">
            <div className="flex items-center gap-3">
              <FolderKanban className="w-5 h-5 text-blue-600" />
              <span className="font-medium">Projects</span>
            </div>
          </Card>
        </Link>
        <Link href="/demo/documents">
          <Card className="p-4 hover:shadow-md transition-shadow cursor-pointer">
            <div className="flex items-center gap-3">
              <FileText className="w-5 h-5 text-purple-600" />
              <span className="font-medium">Documents</span>
            </div>
          </Card>
        </Link>
        <Link href="/demo/alerts">
          <Card className="p-4 hover:shadow-md transition-shadow cursor-pointer">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
              <span className="font-medium">Alerts</span>
            </div>
          </Card>
        </Link>
        <Link href="/demo/stakeholders">
          <Card className="p-4 hover:shadow-md transition-shadow cursor-pointer">
            <div className="flex items-center gap-3">
              <Users className="w-5 h-5 text-green-600" />
              <span className="font-medium">Stakeholders</span>
            </div>
          </Card>
        </Link>
      </div>
    </div>
  );
}
