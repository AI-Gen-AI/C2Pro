/**
 * Test Suite ID: TASK-1427
 * Route Coverage: canonical dashboard route standalone implementation
 */
"use client";

import { useEffect, useState } from "react";
import { Loader2, ArrowLeft, BarChart3, AlertTriangle, FileText } from "lucide-react";
import { DashboardClient } from "@/components/coherence/DashboardClient";
import type { DashboardSummary, ProjectListItem } from "@/lib/api/contracts";
import { getDashboardSummary, listProjects } from "@/lib/api/services/dashboard";
import type { DashboardSummary, ProjectListItem } from "@/lib/api/contracts";
import { useAuthStore } from "@/stores/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function AppDashboardPage() {
  const token = useAuthStore((state) => state.token);
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [summaries, setSummaries] = useState<Record<string, DashboardSummary>>({});
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setProjects([]);
      setSummaries({});
      setLoadError(null);
      setIsLoading(false);
      return;
    }

    let active = true;

    const loadDashboard = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const fetchedProjects = await listProjects();

        if (fetchedProjects.length === 0) {
          if (active) {
            setProjects([]);
            setSummaries({});
            setLoadError(
              "No projects found. Create a project to see coherence data.",
            );
          }
          return;
        }

        if (!active) return;
        setProjects(fetchedProjects);

        // Fetch summaries for all projects
        const summariesMap: Record<string, DashboardSummary> = {};
        await Promise.all(
          fetchedProjects.map(async (p) => {
            try {
              const summary = await getDashboardSummary(p.id);
              summariesMap[p.id] = summary;
            } catch (e) {
              console.error(`Failed to load summary for project ${p.id}`, e);
            }
          })
        );

        if (!active) return;
        setSummaries(summariesMap);
      } catch (error) {
        if (!active) return;
        setLoadError(
          error instanceof Error
            ? error.message
            : "Could not load dashboard data right now.",
        );
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    void loadDashboard();

    return () => {
      active = false;
    };
  }, [token]);

  if (!token) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          Authenticating...
        </span>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[200px] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          Loading dashboard overview...
        </span>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="space-y-5">
        <h1 className="text-[22px] font-semibold text-foreground">
          Coherence Dashboard
        </h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError} Verify the backend coherence endpoints are available.
        </div>
      </div>
    );
  }

  // Drill-down view
  if (selectedProjectId) {
    const project = projects.find((p) => p.id === selectedProjectId);
    const data = summaries[selectedProjectId];

    if (!project || !data) {
      return (
        <div className="space-y-5">
          <Button variant="ghost" onClick={() => setSelectedProjectId(null)} className="-ml-2">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Overview
          </Button>
          <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            Data not available for this project.
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-5">
        <Button variant="ghost" onClick={() => setSelectedProjectId(null)} className="-ml-2 mb-2 text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Overview
        </Button>
        <DashboardClient data={data} projectName={project.name} />
      </div>
    );
  }

  // Overview view
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[22px] font-semibold text-foreground">
          Portfolio Overview
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cross-project coherence and alert distribution.
        </p>
      </div>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => {
          const summary = summaries[project.id];
          const score = summary?.coherence_score ?? 0;
          const alerts = summary?.alert_count ?? 0;
          const docs = summary?.document_count ?? 0;

          return (
            <Card 
              key={project.id} 
              className="cursor-pointer transition-all hover:border-primary/50 hover:shadow-sm"
              onClick={() => setSelectedProjectId(project.id)}
            >
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium leading-tight">
                  {project.name}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="space-y-1 rounded-md bg-muted/50 p-2">
                    <BarChart3 className="mx-auto h-4 w-4 text-primary" />
                    <div className="text-xl font-bold">{score}</div>
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Score</div>
                  </div>
                  <div className="space-y-1 rounded-md bg-muted/50 p-2">
                    <AlertTriangle className={`mx-auto h-4 w-4 ${alerts > 0 ? 'text-warning' : 'text-muted-foreground'}`} />
                    <div className="text-xl font-bold">{alerts}</div>
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Alerts</div>
                  </div>
                  <div className="space-y-1 rounded-md bg-muted/50 p-2">
                    <FileText className="mx-auto h-4 w-4 text-chart-quality" />
                    <div className="text-xl font-bold">{docs}</div>
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Docs</div>
                  </div>
                </div>
                <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Click to view drill-down</span>
                  <span className="text-primary group-hover:underline">View details &rarr;</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
