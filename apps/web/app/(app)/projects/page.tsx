"use client";

import Link from "next/link";
import { useProjects } from "@/hooks/useProjects";
import { ProjectListTable } from "@/components/features/projects/ProjectListTable";
import { useAuthStore } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import { Loader2, Plus } from "lucide-react";

export default function ProjectsPage() {
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, error } = useProjects(!!token);

  const projects = data ?? [];
  const loadError =
    error instanceof Error ? error.message : error ? String(error) : null;

  // Show loading while waiting for auth token
  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          Authenticating...
        </span>
      </div>
    );
  }

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
        <div className="flex items-center gap-4">
          <span className="text-xs text-muted-foreground">
            {isLoading ? "Loading..." : `${projects.length} projects`}
          </span>
          <Button asChild>
            <Link href="/projects/new">
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Link>
          </Button>
        </div>
      </div>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          API request failed ({loadError}). Verify backend API is running at{" "}
          <code>http://localhost:8000/api/v1</code>.
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <ProjectListTable projects={projects} />
      )}
    </div>
  );
}
