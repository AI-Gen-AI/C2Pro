"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PlusCircle, FolderOpen } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const [hasProjects] = useState(false); // GREEN Phase: For first-time users

  // Empty state for first-time users
  if (!hasProjects) {
    return (
      <div
        className="flex min-h-[calc(100vh-200px)] flex-col items-center justify-center p-8"
        data-testid="empty-dashboard"
      >
        <Card className="w-full max-w-md border-dashed">
          <CardContent className="flex flex-col items-center justify-center p-12 text-center">
            <div className="mb-6 rounded-full bg-muted p-6">
              <FolderOpen className="h-12 w-12 text-muted-foreground" />
            </div>
            <h2 className="mb-2 text-2xl font-semibold">No projects yet</h2>
            <p className="mb-6 text-sm text-muted-foreground">
              Get started by creating your first project. Upload contracts,
              extract clauses, and manage your WBS structure.
            </p>
            <Button
              size="lg"
              data-testid="create-first-project-button"
              onClick={() => router.push("/projects/new")}
              className="gap-2"
            >
              <PlusCircle className="h-5 w-5" />
              Create First Project
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // TODO: Show existing projects list
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <p>Your projects will appear here.</p>
    </div>
  );
}
