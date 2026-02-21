/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
"use client";

import { use } from "react";
import { AlertReviewCenter } from "@/components/features/alerts/AlertReviewCenter";
import { demoProjectAlerts } from "@/lib/demo-data/alerts";

interface AlertsPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default function AlertsPage({ params }: AlertsPageProps) {
  const { id } = use(params);

  return (
    <div className="space-y-6">
      <AlertReviewCenter projectId={id} alerts={demoProjectAlerts} />
    </div>
  );
}
