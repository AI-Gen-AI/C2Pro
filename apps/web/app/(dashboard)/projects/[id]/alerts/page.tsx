/**
 * Test Suite ID: S3-04
 * Roadmap Reference: S3-04 Alert Review Center + approve/reject modal
 */
"use client";

import { use } from "react";
import {
  AlertReviewCenter,
  type ReviewAlert,
} from "@/components/features/alerts/AlertReviewCenter";

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

export default function AlertsPage({ params }: AlertsPageProps) {
  const { id } = use(params);

  return (
    <div className="space-y-6">
      <AlertReviewCenter projectId={id} alerts={DEMO_ALERTS} />
    </div>
  );
}
