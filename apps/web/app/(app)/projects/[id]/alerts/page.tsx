/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
"use client";

import { use } from "react";
import { AlertReviewCenter } from "@/components/features/alerts/AlertReviewCenter";
import { useProjectAlerts } from "@/hooks/useProjectAlerts";

interface AlertsPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function AlertsPage({ params }: AlertsPageProps) {
  const { id } = use(params);
  const { alerts, loading, error } = useProjectAlerts(id);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading alerts…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {error.message}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <AlertReviewCenter projectId={id} alerts={alerts} />
    </div>
  );
}
