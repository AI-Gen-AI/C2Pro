/**
 * Test Suite ID: TASK-1427
 * Route Coverage: canonical budget route standalone implementation
 */
"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
} from "lucide-react";

const budgetData = {
  totalBudget: 2500000,
  spent: 1550000,
  remaining: 950000,
  utilization: 62,
  variance: "On Track",
  categories: [
    { name: "Labor", budget: 1200000, spent: 750000, variance: -50000 },
    { name: "Materials", budget: 800000, spent: 520000, variance: 20000 },
    { name: "Equipment", budget: 300000, spent: 180000, variance: -10000 },
    { name: "Subcontractors", budget: 200000, spent: 100000, variance: 0 },
  ],
};

export default function ProjectBudgetPage() {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(amount);
  };

  return (
    <div className="space-y-6" data-testid="budget-page">
      <div>
        <h1 className="text-2xl font-bold">Budget Overview</h1>
        <p className="text-muted-foreground">
          Track budget utilization and spending across categories
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card data-testid="total-budget">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Total Budget
              </span>
            </div>
            <p className="mt-2 text-2xl font-bold">
              {formatCurrency(budgetData.totalBudget)}
            </p>
          </CardContent>
        </Card>

        <Card data-testid="spent-amount">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Spent</span>
            </div>
            <p className="mt-2 text-2xl font-bold">
              {formatCurrency(budgetData.spent)}
            </p>
          </CardContent>
        </Card>

        <Card data-testid="budget-utilization">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Utilization</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{budgetData.utilization}%</p>
          </CardContent>
        </Card>

        <Card data-testid="budget-variance">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">Status</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{budgetData.variance}</p>
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
              <span>{budgetData.utilization}%</span>
            </div>
            <Progress value={budgetData.utilization} className="h-3" />
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <span className="text-muted-foreground">Spent</span>
              <p className="font-semibold">
                {formatCurrency(budgetData.spent)}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-muted-foreground">Remaining</span>
              <p className="font-semibold">
                {formatCurrency(budgetData.remaining)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Category Breakdown</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {budgetData.categories.map((category) => {
            const percentage = (category.spent / category.budget) * 100;
            return (
              <div key={category.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{category.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {formatCurrency(category.spent)} /{" "}
                      {formatCurrency(category.budget)}
                    </span>
                    {category.variance > 0 ? (
                      <Badge variant="destructive" className="text-xs">
                        +{formatCurrency(category.variance)}
                      </Badge>
                    ) : category.variance < 0 ? (
                      <Badge variant="default" className="text-xs bg-green-600">
                        {formatCurrency(category.variance)}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <Progress value={percentage} className="h-2" />
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
