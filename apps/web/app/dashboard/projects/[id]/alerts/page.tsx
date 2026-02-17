/**
 * Test Suite ID: TS-E2E-J2-001
 * Roadmap Reference: Weekly Project Review Journey - Alert Review
 */
"use client";

import { use } from "react";
import { useState } from "react";
import {
  AlertReviewCenter,
  type ReviewAlert,
} from "@/src/components/features/alerts/AlertReviewCenter";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { AlertTriangle, CheckCircle, Clock } from "lucide-react";

interface AlertsPageProps {
  params: Promise<{
    id: string;
  }>;
}

const DEMO_ALERTS: ReviewAlert[] = [
  {
    id: "a-1",
    title: "Delay penalty mismatch",
    severity: "high",
    status: "pending",
    clauseId: "c-101",
    assignee: "legal.reviewer",
  },
  {
    id: "a-2",
    title: "Insurance gap",
    severity: "critical",
    status: "pending",
    clauseId: "c-202",
    assignee: "risk.owner",
  },
];

const mockAlerts = [
  {
    id: "1",
    title: "Contract Penalty Clause Violation Risk",
    severity: "critical",
    category: "Legal",
    description: "Risk of penalty due to delayed milestone completion",
    createdAt: "2 days ago",
    status: "open",
  },
  {
    id: "2",
    title: "Critical Path Delay - Foundation Work",
    severity: "high",
    category: "Timeline",
    description: "Foundation work is 5 days behind schedule",
    createdAt: "3 days ago",
    status: "open",
  },
  {
    id: "3",
    title: "Material Cost Variance",
    severity: "medium",
    category: "Budget",
    description: "Steel costs exceeded estimate by 12%",
    createdAt: "5 days ago",
    status: "open",
  },
  {
    id: "4",
    title: "Inspection Schedule Conflict",
    severity: "high",
    category: "Timeline",
    description: "City inspector unavailable on scheduled date",
    createdAt: "1 week ago",
    status: "open",
  },
];

const mockResolvedAlerts = [
  {
    id: "5",
    title: "Contract Penalty Clause Violation Risk",
    severity: "critical",
    category: "Legal",
    description: "Risk of penalty due to delayed milestone completion",
    resolvedAt: "2 weeks ago",
    status: "resolved",
    resolution: "Issue resolved - contractor provided updated schedule",
  },
];

export default function AlertsPage({ params }: AlertsPageProps) {
  const { id } = use(params);
  const [selectedSeverity, setSelectedSeverity] = useState<string>("all");
  const [activeTab, setActiveTab] = useState<"open" | "resolved">("open");
  const [resolveDialogOpen, setResolveDialogOpen] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<
    (typeof mockAlerts)[0] | null
  >(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolutionType, setResolutionType] = useState("");

  const filteredAlerts = mockAlerts.filter((alert) => {
    if (selectedSeverity === "all") return true;
    return alert.severity === selectedSeverity;
  });

  const handleResolveClick = (alert: (typeof mockAlerts)[0]) => {
    setSelectedAlert(alert);
    setResolveDialogOpen(true);
  };

  const handleConfirmResolve = () => {
    setResolveDialogOpen(false);
    setResolutionNotes("");
    setResolutionType("");
    setSelectedAlert(null);
  };

  return (
    <div className="space-y-6" data-testid="alerts-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Alerts</h1>
          <p className="text-muted-foreground">
            Monitor and manage project alerts and notifications
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b">
        <button
          className={`pb-2 text-sm font-medium ${
            activeTab === "open"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground"
          }`}
          onClick={() => setActiveTab("open")}
          data-testid="open-alerts-tab"
        >
          Open Alerts ({mockAlerts.length})
        </button>
        <button
          className={`pb-2 text-sm font-medium ${
            activeTab === "resolved"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground"
          }`}
          onClick={() => setActiveTab("resolved")}
          data-testid="resolved-alerts-tab"
        >
          Resolved
        </button>
      </div>

      {/* Filter */}
      {activeTab === "open" && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            Filter by severity:
          </span>
          <Select value={selectedSeverity} onValueChange={setSelectedSeverity}>
            <SelectTrigger
              className="w-[180px]"
              data-testid="alert-severity-filter"
            >
              <SelectValue placeholder="Select severity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severities</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {/* Open Alerts */}
      {activeTab === "open" && (
        <div className="space-y-4" data-testid="open-alerts-section">
          {filteredAlerts.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center p-8 text-center">
                <CheckCircle className="mb-4 h-12 w-12 text-green-500" />
                <p className="text-lg font-medium">No alerts found</p>
                <p className="text-sm text-muted-foreground">
                  All alerts have been filtered out or resolved
                </p>
              </CardContent>
            </Card>
          ) : (
            filteredAlerts.map((alert) => (
              <Card
                key={alert.id}
                className="relative overflow-hidden"
                data-testid={`alert-item-${alert.id}`}
                data-severity={alert.severity}
              >
                <div
                  className={`absolute left-0 top-0 h-full w-1 ${
                    alert.severity === "critical"
                      ? "bg-destructive"
                      : alert.severity === "high"
                        ? "bg-warning"
                        : "bg-yellow-400"
                  }`}
                />
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div
                        className={`rounded-full p-2 ${
                          alert.severity === "critical"
                            ? "bg-destructive/10"
                            : alert.severity === "high"
                              ? "bg-warning/10"
                              : "bg-yellow-400/10"
                        }`}
                        data-testid={`alert-${alert.severity}`}
                      >
                        <AlertTriangle
                          className={`h-5 w-5 ${
                            alert.severity === "critical"
                              ? "text-destructive"
                              : alert.severity === "high"
                                ? "text-warning"
                                : "text-yellow-600"
                          }`}
                        />
                      </div>
                      <div>
                        <h3 className="font-semibold">{alert.title}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {alert.description}
                        </p>
                        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                          <Badge variant="outline">{alert.category}</Badge>
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {alert.createdAt}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          alert.severity === "critical"
                            ? "destructive"
                            : alert.severity === "high"
                              ? "warning"
                              : "secondary"
                        }
                      >
                        {alert.severity}
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        data-testid="resolve-button"
                        onClick={() => handleResolveClick(alert)}
                      >
                        Resolve
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Resolved Alerts */}
      {activeTab === "resolved" && (
        <div className="space-y-4" data-testid="resolved-alerts-section">
          {mockResolvedAlerts.map((alert) => (
            <Card
              key={alert.id}
              className="relative overflow-hidden opacity-75"
            >
              <div className="absolute left-0 top-0 h-full w-1 bg-green-500" />
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4">
                    <div className="rounded-full bg-green-100 p-2">
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{alert.title}</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {alert.resolution}
                      </p>
                      <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                        <Badge variant="outline">{alert.category}</Badge>
                        <span>Resolved {alert.resolvedAt}</span>
                      </div>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-green-600">
                    Resolved
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Also render the existing AlertReviewCenter for demo purposes */}
      <div className="pt-8 border-t">
        <h2 className="text-lg font-semibold mb-4">Alert Review Center</h2>
        <AlertReviewCenter projectId={id} alerts={DEMO_ALERTS} />
      </div>

      {/* Resolve Dialog */}
      <Dialog open={resolveDialogOpen} onOpenChange={setResolveDialogOpen}>
        <DialogContent data-testid="resolve-alert-dialog">
          <DialogHeader>
            <DialogTitle>Resolve Alert</DialogTitle>
            <DialogDescription>
              Provide details about how this alert was resolved
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Resolution Type</label>
              <Select value={resolutionType} onValueChange={setResolutionType}>
                <SelectTrigger data-testid="resolution-type">
                  <SelectValue placeholder="Select resolution type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mitigated">Mitigated</SelectItem>
                  <SelectItem value="resolved">Resolved</SelectItem>
                  <SelectItem value="accepted">Accepted Risk</SelectItem>
                  <SelectItem value="false-positive">False Positive</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Resolution Notes</label>
              <Textarea
                placeholder="Describe how this alert was resolved..."
                value={resolutionNotes}
                onChange={(e) => setResolutionNotes(e.target.value)}
                data-testid="resolution-notes"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setResolveDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirmResolve}
              data-testid="confirm-resolve"
            >
              Confirm Resolution
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
