"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { DashboardClient } from "@/components/coherence/DashboardClient";
import type { DashboardSummary } from "@/lib/api/contracts";
import { getCoherenceDashboardApiCoherenceDashboardProjectIdGet } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { listProjectsApiV1ProjectsGet } from "@/lib/api/generated/projects/projects";
import { useAuthStore } from "@/stores/auth";

export default function DashboardPage() {
  const token = useAuthStore((state) => state.token);
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [projectName, setProjectName] = useState("");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      setData(null);
      setProjectName("");
      setLoadError(null);
      setIsLoading(false);
      return;
    }

    let active = true;

    const loadDashboard = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const projectsResponse = await listProjectsApiV1ProjectsGet();
        const first = projectsResponse.items?.[0];

        if (!first) {
          if (active) {
            setData(null);
            setProjectName("");
            setLoadError(
              "No projects found. Create a project to see coherence data.",
            );
          }
          return;
        }

        const summary =
          await getCoherenceDashboardApiCoherenceDashboardProjectIdGet(first.id);

        if (!active) {
          return;
        }

        setProjectName(first.name);
        setData({
          project_id: String(summary.project_id ?? first.id),
          tenant_id: String(summary.tenant_id ?? ""),
          coherence_score: Number(
            summary.coherence_score ?? summary.global_score ?? 0,
          ),
          global_score: Number(
            summary.global_score ?? summary.coherence_score ?? 0,
          ),
          sub_scores: normalizeNumberMap(summary.sub_scores),
          weights_used: normalizeNumberMap(summary.weights_used),
          alert_count: Number(summary.alert_count ?? 0),
          document_count: Number(summary.document_count ?? 0),
          methodology_version: String(summary.methodology_version ?? "unknown"),
          last_updated:
            typeof summary.last_updated === "string"
              ? summary.last_updated
              : null,
        });
      } catch (error) {
        if (!active) {
          return;
        }

        setData(null);
        setProjectName("");
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
          Loading dashboard...
        </span>
      </div>
    );
  }

  if (loadError || !data) {
    return (
      <div className="space-y-5">
        <h1 className="text-[22px] font-semibold text-foreground">
          Coherence Dashboard
        </h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError ?? "No data available."} Verify the backend coherence endpoints are available.
        </div>
      </div>
    );
  }

  return <DashboardClient data={data} projectName={projectName} />;
}

function normalizeNumberMap(value: unknown): Record<string, number> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, entry]) => [key, Number(entry ?? 0)]),
  );
}
