"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Gauge,
  AlertTriangle,
  FileText,
  DollarSign,
  ArrowRight,
  ChevronRight,
  ChevronLeft,
  X,
  FolderTree,
} from "lucide-react";

const stats = [
  {
    label: "Coherence Score",
    value: "78",
    icon: Gauge,
    color: "text-primary",
    testId: "coherence-score-card",
  },
  {
    label: "Open Alerts",
    value: "7",
    icon: AlertTriangle,
    color: "text-warning",
    testId: "open-alerts-card",
  },
  {
    label: "Documents",
    value: "12",
    icon: FileText,
    color: "text-chart-quality",
    testId: "completion-progress-card",
  },
  {
    label: "Budget Used",
    value: "62%",
    icon: DollarSign,
    color: "text-chart-budget",
    testId: "budget-utilization-card",
  },
];

const tourSteps = [
  {
    id: 1,
    title: "Welcome to Your New Project!",
    description:
      "Your project has been created successfully. Let us show you around.",
    icon: FolderTree,
  },
  {
    id: 2,
    title: "Explore your WBS structure",
    description:
      "View and manage your Work Breakdown Structure to track project progress.",
    icon: FolderTree,
  },
  {
    id: 3,
    title: "Monitor Alerts",
    description:
      "Keep an eye on alerts and notifications to stay on top of issues.",
    icon: AlertTriangle,
  },
];

export default function ProjectOverviewPage() {
  const [showTour, setShowTour] = useState(false);
  const [currentTourStep, setCurrentTourStep] = useState(0);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  const [showCoherenceModal, setShowCoherenceModal] = useState(false);

  useEffect(() => {
    // Show success notification and tour on first load
    setShowSuccessNotification(true);
    const timer = setTimeout(() => {
      setShowTour(true);
    }, 1000);
    return () => clearTimeout(timer);
  }, []);

  const handleNextTourStep = () => {
    if (currentTourStep < tourSteps.length - 1) {
      setCurrentTourStep(currentTourStep + 1);
    } else {
      setShowTour(false);
    }
  };

  const handleSkipTour = () => {
    setShowTour(false);
  };

  const currentStep = tourSteps[currentTourStep];
  const Icon = currentStep?.icon || FolderTree;

  return (
    <div className="space-y-5" data-testid="project-dashboard">
      {/* Success Notification */}
      {showSuccessNotification && (
        <div
          className="rounded-lg bg-green-100 p-4 text-green-800"
          data-testid="success-notification"
        >
          <p className="font-medium">Project created successfully!</p>
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const StatIcon = stat.icon;
          return (
            <Card
              key={stat.label}
              className="card-interactive cursor-pointer"
              data-testid={stat.testId}
              onClick={() => {
                if (stat.label === "Coherence Score") {
                  setShowCoherenceModal(true);
                }
              }}
            >
              <CardContent className="flex items-center gap-4 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted">
                  <StatIcon
                    className={`h-5 w-5 ${stat.color}`}
                    strokeWidth={1.5}
                  />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    {stat.label}
                  </p>
                  <p
                    className="font-mono text-2xl font-bold"
                    data-testid={`${stat.testId.replace("-card", "-value")}`}
                  >
                    {stat.value}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Project Summary & Alerts */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">
              Project Summary
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="flex justify-between">
              <span>Status</span>
              <Badge variant="default">Active</Badge>
            </div>
            <div className="flex justify-between">
              <span>Budget Utilization</span>
              <span className="font-mono font-medium text-foreground">62%</span>
            </div>
            <Progress value={62} className="h-1.5" />
            <div className="flex justify-between">
              <span>Completion</span>
              <span className="font-mono font-medium text-foreground">45%</span>
            </div>
            <Progress value={45} className="h-1.5" />
            <div className="flex justify-between">
              <span>Timeline</span>
              <span className="text-foreground">Jan 2025 - Dec 2026</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">
                Recent Alerts
              </CardTitle>
              <Link
                href="#"
                className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                View All <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {[
              {
                severity: "critical",
                title: "Contract Penalty Clause Violation Risk",
              },
              {
                severity: "high",
                title: "Critical Path Delay - Foundation Work",
              },
              { severity: "medium", title: "Material Cost Variance" },
            ].map((alert, i) => (
              <div
                key={i}
                className="flex items-center gap-3 rounded-md border p-2.5 text-sm"
              >
                <div
                  className={`h-2 w-2 shrink-0 rounded-full ${
                    alert.severity === "critical"
                      ? "bg-destructive animate-pulse-critical"
                      : alert.severity === "high"
                        ? "bg-warning"
                        : "bg-warning/60"
                  }`}
                />
                <span className="flex-1 text-sm">{alert.title}</span>
                <Badge
                  variant={
                    alert.severity === "critical"
                      ? "destructive"
                      : alert.severity === "high"
                        ? "warning"
                        : "secondary"
                  }
                  className="text-[10px]"
                >
                  {alert.severity}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Coherence Breakdown Modal */}
      <Dialog open={showCoherenceModal} onOpenChange={setShowCoherenceModal}>
        <DialogContent
          className="sm:max-w-lg"
          data-testid="coherence-breakdown-modal"
        >
          <DialogHeader>
            <DialogTitle>Coherence Score Breakdown</DialogTitle>
            <DialogDescription>
              Detailed breakdown of coherence scores by category
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div
              className="flex items-center justify-between"
              data-testid="scope-score"
            >
              <span>Scope</span>
              <span className="font-bold text-green-600">80%</span>
            </div>
            <div
              className="flex items-center justify-between"
              data-testid="budget-score"
            >
              <span>Budget</span>
              <span className="font-bold text-yellow-600">62%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Timeline</span>
              <span className="font-bold text-green-600">75%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Quality</span>
              <span className="font-bold text-green-600">85%</span>
            </div>
            <div className="flex items-center justify-between">
              <span>Legal</span>
              <span className="font-bold text-green-600">90%</span>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Onboarding Tour Modal */}
      <Dialog open={showTour} onOpenChange={setShowTour}>
        <DialogContent
          className="sm:max-w-md"
          data-testid="onboarding-tour-modal"
        >
          <DialogHeader>
            <div className="flex items-center justify-between">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Icon className="h-6 w-6 text-primary" />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleSkipTour}
                data-testid="tour-skip-button"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <DialogTitle
              className="text-xl"
              data-testid={`tour-step-${currentStep.id}`}
            >
              {currentStep.title}
            </DialogTitle>
            <DialogDescription>{currentStep.description}</DialogDescription>
          </DialogHeader>

          <div className="flex items-center justify-center gap-2 py-4">
            {tourSteps.map((_, index) => (
              <div
                key={index}
                className={`h-2 w-2 rounded-full ${
                  index === currentTourStep ? "bg-primary" : "bg-muted"
                }`}
              />
            ))}
          </div>

          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={() =>
                setCurrentTourStep(Math.max(0, currentTourStep - 1))
              }
              disabled={currentTourStep === 0}
              className="gap-2"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </Button>

            <div className="flex gap-2">
              <Button variant="ghost" onClick={handleSkipTour}>
                Skip Tour
              </Button>
              <Button
                onClick={handleNextTourStep}
                className="gap-2"
                data-testid="tour-next-button"
              >
                {currentTourStep === tourSteps.length - 1 ? "Finish" : "Next"}
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
