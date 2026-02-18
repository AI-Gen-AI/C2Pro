"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Grid3X3, Download, Filter } from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";

// Sample RACI data
const raciData = {
  activities: [
    {
      id: "act-1",
      name: "Contract Review & Approval",
      responsible: ["Dr. Sarah Johnson"],
      accountable: ["Michael Chen"],
      consulted: ["Emma Rodriguez"],
      informed: ["James Wilson", "Priya Patel"],
    },
    {
      id: "act-2",
      name: "Technical Specifications",
      responsible: ["Emma Rodriguez"],
      accountable: ["Dr. Sarah Johnson"],
      consulted: ["James Wilson"],
      informed: ["Michael Chen", "Priya Patel"],
    },
    {
      id: "act-3",
      name: "Procurement Execution",
      responsible: ["Michael Chen"],
      accountable: ["Dr. Sarah Johnson"],
      consulted: ["Priya Patel"],
      informed: ["Emma Rodriguez", "James Wilson"],
    },
    {
      id: "act-4",
      name: "Quality Assurance",
      responsible: ["Emma Rodriguez"],
      accountable: ["James Wilson"],
      consulted: ["Dr. Sarah Johnson"],
      informed: ["Michael Chen", "Priya Patel"],
    },
    {
      id: "act-5",
      name: "Budget Management",
      responsible: ["Priya Patel"],
      accountable: ["Dr. Sarah Johnson"],
      consulted: ["Michael Chen"],
      informed: ["Emma Rodriguez", "James Wilson"],
    },
    {
      id: "act-6",
      name: "Site Operations",
      responsible: ["James Wilson"],
      accountable: ["Dr. Sarah Johnson"],
      consulted: ["Emma Rodriguez"],
      informed: ["Michael Chen", "Priya Patel"],
    },
  ],
};

function getRoleBadge(role: string) {
  switch (role) {
    case "R":
      return (
        <Badge className="bg-blue-100 text-blue-700 font-bold w-8 h-8 flex items-center justify-center">
          R
        </Badge>
      );
    case "A":
      return (
        <Badge className="bg-red-100 text-red-700 font-bold w-8 h-8 flex items-center justify-center">
          A
        </Badge>
      );
    case "C":
      return (
        <Badge className="bg-yellow-100 text-yellow-700 font-bold w-8 h-8 flex items-center justify-center">
          C
        </Badge>
      );
    case "I":
      return (
        <Badge className="bg-gray-100 text-gray-700 font-bold w-8 h-8 flex items-center justify-center">
          I
        </Badge>
      );
    default:
      return null;
  }
}

export default function DemoRaciPage() {
  const stakeholders = SAMPLE_DATA.stakeholders;

  const getStakeholderRole = (
    activity: (typeof raciData.activities)[0],
    stakeholderName: string
  ): string | null => {
    if (activity.responsible.includes(stakeholderName)) return "R";
    if (activity.accountable.includes(stakeholderName)) return "A";
    if (activity.consulted.includes(stakeholderName)) return "C";
    if (activity.informed.includes(stakeholderName)) return "I";
    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">RACI Matrix</h1>
          <p className="text-sm text-muted-foreground">
            Responsibility Assignment Matrix for project activities
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled>
            <Filter className="w-4 h-4 mr-2" />
            Filter
          </Button>
          <Button variant="outline" size="sm" disabled>
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Demo RACI matrix showing sample responsibility assignments. Sign in to
          create and manage your own RACI matrices.
        </p>
      </div>

      {/* Legend */}
      <Card className="p-4">
        <h3 className="font-medium text-sm mb-3">Legend</h3>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2">
            {getRoleBadge("R")}
            <span className="text-sm">
              <strong>R</strong>esponsible - Does the work
            </span>
          </div>
          <div className="flex items-center gap-2">
            {getRoleBadge("A")}
            <span className="text-sm">
              <strong>A</strong>ccountable - Final approver
            </span>
          </div>
          <div className="flex items-center gap-2">
            {getRoleBadge("C")}
            <span className="text-sm">
              <strong>C</strong>onsulted - Provides input
            </span>
          </div>
          <div className="flex items-center gap-2">
            {getRoleBadge("I")}
            <span className="text-sm">
              <strong>I</strong>nformed - Kept updated
            </span>
          </div>
        </div>
      </Card>

      {/* RACI Matrix Table */}
      <Card className="p-4 overflow-x-auto">
        <table className="w-full min-w-[800px]">
          <thead>
            <tr className="border-b">
              <th className="text-left py-3 px-4 font-semibold text-sm">
                Activity
              </th>
              {stakeholders.map((s) => (
                <th
                  key={s.id}
                  className="text-center py-3 px-2 font-semibold text-sm"
                >
                  <div className="flex flex-col items-center">
                    <span className="truncate max-w-[100px]">{s.name.split(" ")[0]}</span>
                    <span className="text-xs text-muted-foreground font-normal truncate max-w-[100px]">
                      {s.role}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {raciData.activities.map((activity, idx) => (
              <tr
                key={activity.id}
                className={idx % 2 === 0 ? "bg-slate-50" : ""}
              >
                <td className="py-3 px-4 text-sm font-medium">
                  {activity.name}
                </td>
                {stakeholders.map((s) => {
                  const role = getStakeholderRole(activity, s.name);
                  return (
                    <td key={s.id} className="text-center py-3 px-2">
                      {role && getRoleBadge(role)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            {getRoleBadge("R")}
            <span className="font-medium">Responsible</span>
          </div>
          <p className="text-2xl font-bold">{raciData.activities.length}</p>
          <p className="text-xs text-muted-foreground">Total assignments</p>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            {getRoleBadge("A")}
            <span className="font-medium">Accountable</span>
          </div>
          <p className="text-2xl font-bold">{raciData.activities.length}</p>
          <p className="text-xs text-muted-foreground">Total assignments</p>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            {getRoleBadge("C")}
            <span className="font-medium">Consulted</span>
          </div>
          <p className="text-2xl font-bold">{raciData.activities.length}</p>
          <p className="text-xs text-muted-foreground">Total assignments</p>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-2">
            {getRoleBadge("I")}
            <span className="font-medium">Informed</span>
          </div>
          <p className="text-2xl font-bold">
            {raciData.activities.reduce(
              (sum, a) => sum + a.informed.length,
              0
            )}
          </p>
          <p className="text-xs text-muted-foreground">Total assignments</p>
        </Card>
      </div>
    </div>
  );
}
