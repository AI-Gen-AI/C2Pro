/**
 * Test Suite ID: TASK-1487
 * Route Coverage: canonical budget route uses backend budget data
 */
"use client";

import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { AlertTriangle, DollarSign, TrendingDown, TrendingUp } from "lucide-react";
import { useGetProjectBudgetApiV1ProjectsProjectIdBudgetGet } from "@/lib/api/generated/projects/projects";

type BudgetResponseLike = Record<string, unknown>;

function readNumber(data: BudgetResponseLike | undefined, ...keys: string[]) {
  for (const key of keys) {
    const value = data?.[key];
    if (typeof value === "number") {
      return value;
    }
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);
      if (!Number.isNaN(parsed)) {
        return parsed;
      }
    }
  }
  return 0;
}

function readString(data: BudgetResponseLike | undefined, ...keys: string[]) {
  for (const key of keys) {
    const value = data?.[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return "";
}

export default function ProjectBudgetPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { data, isLoading, error } =
    useGetProjectBudgetApiV1ProjectsProjectIdBudgetGet(projectId, undefined);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading budget…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {error instanceof Error ? error.message : "Failed to load budget"}
      </div>
    );
  }

  const budget = (data ?? {}) as BudgetResponseLike;
  const totalBudget = readNumber(budget, "total_budget", "totalBudget", "budget_total");
  const spentAmount = readNumber(budget, "spent_amount", "spent", "spentAmount");
  const utilization = readNumber(
    budget,
    "utilization_percentage",
    "utilization",
    "utilizationPercent",
  );
  const variance = readString(
    budget,
    "variance_status",
    "variance",
    "status",
  );
  const remainingBudget = Math.max(totalBudget - spentAmount, 0);
  const safeUtilization =
    utilization > 0 ? utilization : totalBudget > 0 ? Math.round((spentAmount / totalBudget) * 100) : 0;
  const varianceLabel = variance || "Unknown";
  const currency = readString(budget, "currency") || "EUR";

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);

  return (
    <div className="space-y-6" data-testid="budget-page">
      <div>
        <h1 className="text-2xl font-bold">Budget Overview</h1>
        <p className="text-muted-foreground">
          Track budget utilization from the live backend budget endpoint.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card data-testid="total-budget">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Total Budget</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{formatCurrency(totalBudget)}</p>
          </CardContent>
        </Card>

        <Card data-testid="spent-amount">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Spent</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{formatCurrency(spentAmount)}</p>
          </CardContent>
        </Card>

        <Card data-testid="budget-utilization">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Utilization</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{safeUtilization}%</p>
          </CardContent>
        </Card>

        <Card data-testid="budget-variance">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Status</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{varianceLabel}</p>
          </CardContent>
        </Card>
      </div>

      <Card data-testid="budget-chart">
        <CardHeader>
          <CardTitle>Budget Utilization</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Overall Progress</span>
              <span>{safeUtilization}%</span>
            </div>
            <Progress value={safeUtilization} className="h-3" />
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <span className="text-muted-foreground">Spent</span>
              <p className="font-semibold">{formatCurrency(spentAmount)}</p>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground">Remaining</span>
              <p className="font-semibold">{formatCurrency(remainingBudget)}</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
