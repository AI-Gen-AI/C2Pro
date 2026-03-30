'use client';

import { useRouter } from 'next/navigation';
import { ArrowRight, FileSearch } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useListProjectsApiV1ProjectsGet } from '@/lib/api/generated/projects/projects';

/**
 * Test Suite ID: TASK-1347
 * Top-level evidence route uses backend project data for navigation.
 */
export default function EvidencePage() {
  const router = useRouter();
  const { data, isLoading, error } = useListProjectsApiV1ProjectsGet();
  const projects = data?.items ?? [];

  return (
    <div className="mx-auto flex h-full w-full max-w-5xl items-center justify-center px-6 py-10">
      <div className="w-full space-y-6">
        <div className="space-y-3 text-center">
          <div className="flex justify-center">
            <div className="rounded-full bg-primary/10 p-6">
              <FileSearch className="h-12 w-12 text-primary" />
            </div>
          </div>
          <h2 className="text-2xl font-bold">Evidence Review</h2>
          <p className="mx-auto max-w-2xl text-muted-foreground">
            Evidence review is organized by project. Choose a live project to inspect documents,
            extracted data, and approval workflows.
          </p>
        </div>

        {isLoading ? (
          <div className="rounded-xl border bg-card p-6 text-center text-sm text-muted-foreground">
            Loading evidence projects...
          </div>
        ) : error ? (
          <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
            <p className="font-medium text-destructive">
              {error instanceof Error
                ? error.message
                : 'Could not load evidence projects right now.'}
            </p>
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-xl border bg-card p-6 text-center">
            <p className="font-medium">No projects found.</p>
            <p className="mt-2 text-sm text-muted-foreground">
              Create a project first to start reviewing evidence.
            </p>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {projects.map((project) => (
              <div
                key={project.id}
                className="rounded-2xl border bg-card p-5 shadow-sm"
              >
                <div className="space-y-2">
                  <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                    {project.status ?? 'active'}
                  </p>
                  <h3 className="text-lg font-semibold">{project.name}</h3>
                  {project.code ? (
                    <p className="text-sm text-muted-foreground">Code: {project.code}</p>
                  ) : null}
                </div>
                <div className="mt-4 flex gap-2">
                  <Button onClick={() => router.push(`/projects/${project.id}/evidence`)}>
                    <ArrowRight className="mr-2 h-4 w-4" />
                    Open {project.name} Evidence
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:justify-center">
          <Button variant="outline" onClick={() => router.push('/projects')}>
            Go to Projects
          </Button>
          <Button variant="outline" onClick={() => router.push('/documents')}>
            View All Documents
          </Button>
        </div>
      </div>
    </div>
  );
}
