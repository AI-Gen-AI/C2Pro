"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, Circle, Loader2, AlertCircle } from "lucide-react";
import { handleAuthErrorStatus } from "@/lib/api/client";
import { getStreamProjectProcessingUrl } from "@/lib/api/analysis-stream";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/stores/auth";

export interface AnalysisNode {
  id: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "error";
}

const NODES: AnalysisNode[] = [
  {
    id: "document_ingestion",
    name: "N1",
    description: "Document Ingestion",
    status: "pending",
  },
  {
    id: "pii_anonymizer",
    name: "N2",
    description: "PII Anonymization",
    status: "pending",
  },
  {
    id: "router",
    name: "N3",
    description: "Analysis Router",
    status: "pending",
  },
  {
    id: "risk_extractor",
    name: "N4",
    description: "Risk Extraction",
    status: "pending",
  },
  {
    id: "wbs_extractor",
    name: "N5",
    description: "WBS Extraction",
    status: "pending",
  },
  {
    id: "stakeholder_extractor",
    name: "N6",
    description: "Stakeholder Extraction",
    status: "pending",
  },
  {
    id: "raci_generator",
    name: "N7",
    description: "RACI Generator",
    status: "pending",
  },
  {
    id: "coherence_scorer",
    name: "N8",
    description: "Coherence Scoring",
    status: "pending",
  },
  {
    id: "budget_parser",
    name: "N9",
    description: "Budget Parsing",
    status: "pending",
  },
  {
    id: "knowledge_graph_builder",
    name: "N10",
    description: "Knowledge Graph",
    status: "pending",
  },
  {
    id: "decision_intelligence",
    name: "N11",
    description: "Decision Intelligence",
    status: "pending",
  },
  {
    id: "critique",
    name: "N12",
    description: "Quality Critique",
    status: "pending",
  },
  {
    id: "human_interrupt",
    name: "N13",
    description: "Human-in-the-Loop",
    status: "pending",
  },
  {
    id: "citation_validator",
    name: "N15",
    description: "Citation Validation",
    status: "pending",
  },
  {
    id: "final_assembler",
    name: "N16",
    description: "Final Assembly",
    status: "pending",
  },
  {
    id: "save_to_db",
    name: "N17",
    description: "Persistence",
    status: "pending",
  },
];

interface AnalysisProgressTrackerProps {
  projectId: string;
  onComplete?: (result: unknown) => void;
  onError?: (error: string) => void;
}

export function AnalysisProgressTracker({
  projectId,
  onComplete,
  onError,
}: AnalysisProgressTrackerProps) {
  const [nodes, setNodes] = useState<AnalysisNode[]>(NODES);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [overallProgress, setOverallProgress] = useState(0);
  const [error, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    const { token } = useAuthStore.getState();
    const eventSource = new EventSource(
      getStreamProjectProcessingUrl(
        projectId,
        token ? { access_token: token } : undefined,
      ),
    );

    eventSource.addEventListener("stage", (event) => {
      try {
        const data = JSON.parse(event.data);
        const node = NODES[Math.max(0, (data.stage ?? 1) - 1)];
        if (node) {
          updateNodeStatus(node.id, "completed");
          setCurrentStep(data.name || node.name);
        }
        setOverallProgress(data.progress ?? 0);
      } catch (e) {
        console.error("Error parsing SSE data", e);
      }
    });

    eventSource.addEventListener("complete", (event) => {
      try {
        const data = JSON.parse(event.data);
        setOverallProgress(100);
        if (onComplete) onComplete(data);
        eventSource.close();
      } catch (e) {
        console.error("Error parsing completion data", e);
      }
    });

    eventSource.onerror = () => {
      const hasToken = !!useAuthStore.getState().token;
      const message = hasToken
        ? "Processing stream interrupted"
        : "Session expired";
      setLocalError(message);
      if (!hasToken) {
        handleAuthErrorStatus(401);
      }
      if (onError) onError(message);
    };

    return () => eventSource.close();
  }, [projectId]);

  const updateNodeStatus = (nodeId: string, status: AnalysisNode["status"]) => {
    setNodes((prev) =>
      prev.map((node) => (node.id === nodeId ? { ...node, status } : node)),
    );
  };

  return (
    <div className="space-y-6 rounded-xl border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <h3 className="text-lg font-semibold">LLM Orchestration Progress</h3>
          <p className="text-sm text-muted-foreground">
            Processing through 17-node LangGraph pipeline
          </p>
        </div>
        <Badge
          variant={error ? "destructive" : "outline"}
          className="px-3 py-1"
        >
          {error
            ? "Failed"
            : overallProgress === 100
              ? "Completed"
              : "In Progress"}
        </Badge>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm font-medium">
          <span>
            {error
              ? error
              : currentStep
                ? `Currently: ${currentStep}`
                : "Starting..."}
          </span>
          <span>{Math.round(overallProgress)}%</span>
        </div>
        <Progress value={overallProgress} className="h-2" />
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-9">
        {nodes.map((node) => (
          <div
            key={node.id}
            className={`flex flex-col items-center gap-1 rounded-lg border p-2 text-center transition-colors ${
              node.status === "completed"
                ? "border-primary/20 bg-primary/5"
                : node.status === "running"
                  ? "border-primary animate-pulse"
                  : node.status === "error"
                    ? "border-destructive/20 bg-destructive/5"
                    : "border-muted bg-muted/30"
            }`}
            title={node.description}
          >
            <div className="mb-1">
              {node.status === "completed" && (
                <CheckCircle2 className="h-4 w-4 text-primary" />
              )}
              {node.status === "running" && (
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
              )}
              {node.status === "pending" && (
                <Circle className="h-4 w-4 text-muted-foreground" />
              )}
              {node.status === "error" && (
                <AlertCircle className="h-4 w-4 text-destructive" />
              )}
            </div>
            <span
              className={`text-[10px] font-bold uppercase tracking-wider ${
                node.status === "completed" || node.status === "running"
                  ? "text-primary"
                  : "text-muted-foreground"
              }`}
            >
              {node.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
