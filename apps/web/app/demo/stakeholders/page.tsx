"use client";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Users,
  UserPlus,
  Building2,
  Briefcase,
  Target,
} from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";

function getPowerBadge(level: string) {
  switch (level) {
    case "high":
      return <Badge className="bg-red-100 text-red-700">High Power</Badge>;
    case "medium":
      return <Badge className="bg-yellow-100 text-yellow-700">Medium Power</Badge>;
    default:
      return <Badge className="bg-green-100 text-green-700">Low Power</Badge>;
  }
}

function getInterestBadge(level: string) {
  switch (level) {
    case "high":
      return <Badge className="bg-blue-100 text-blue-700">High Interest</Badge>;
    case "medium":
      return <Badge className="bg-slate-100 text-slate-700">Medium Interest</Badge>;
    default:
      return <Badge className="bg-gray-100 text-gray-700">Low Interest</Badge>;
  }
}

function getQuadrantInfo(quadrant: string) {
  switch (quadrant) {
    case "manage_closely":
      return {
        label: "Manage Closely",
        color: "bg-red-500",
        description: "High power, high interest - Key players",
      };
    case "keep_satisfied":
      return {
        label: "Keep Satisfied",
        color: "bg-orange-500",
        description: "High power, low interest - Meet their needs",
      };
    case "keep_informed":
      return {
        label: "Keep Informed",
        color: "bg-blue-500",
        description: "Low power, high interest - Show consideration",
      };
    default:
      return {
        label: "Monitor",
        color: "bg-gray-500",
        description: "Low power, low interest - Minimal effort",
      };
  }
}

export default function DemoStakeholdersPage() {
  const stakeholders = SAMPLE_DATA.stakeholders;

  // Group by quadrant for the matrix
  const byQuadrant = {
    manage_closely: stakeholders.filter((s) => s.quadrant === "manage_closely"),
    keep_satisfied: stakeholders.filter((s) => s.quadrant === "keep_satisfied"),
    keep_informed: stakeholders.filter((s) => s.quadrant === "keep_informed"),
    monitor: stakeholders.filter((s) => s.quadrant === "monitor"),
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Stakeholders</h1>
          <p className="text-sm text-muted-foreground">
            Project stakeholder analysis and power/interest matrix
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            {stakeholders.length} stakeholders
          </span>
          <Button disabled className="opacity-50 cursor-not-allowed">
            <UserPlus className="w-4 h-4 mr-2" />
            Add Stakeholder
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Demo stakeholder matrix showing sample project participants. Sign in to manage your own stakeholders.
        </p>
      </div>

      {/* Power/Interest Matrix */}
      <Card className="p-4">
        <h2 className="font-semibold text-foreground mb-4 flex items-center gap-2">
          <Target className="w-5 h-5" />
          Power/Interest Matrix
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {/* Manage Closely (High Power, High Interest) */}
          <div className="p-4 border-2 border-red-200 bg-red-50 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span className="font-medium text-red-800">Manage Closely</span>
            </div>
            <p className="text-xs text-red-600 mb-3">High Power, High Interest</p>
            <div className="space-y-2">
              {byQuadrant.manage_closely.map((s) => (
                <div key={s.id} className="p-2 bg-white rounded border border-red-200">
                  <p className="font-medium text-sm">{s.name}</p>
                  <p className="text-xs text-muted-foreground">{s.role}</p>
                </div>
              ))}
              {byQuadrant.manage_closely.length === 0 && (
                <p className="text-xs text-muted-foreground italic">No stakeholders</p>
              )}
            </div>
          </div>

          {/* Keep Satisfied (High Power, Low Interest) */}
          <div className="p-4 border-2 border-orange-200 bg-orange-50 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 rounded-full bg-orange-500" />
              <span className="font-medium text-orange-800">Keep Satisfied</span>
            </div>
            <p className="text-xs text-orange-600 mb-3">High Power, Low Interest</p>
            <div className="space-y-2">
              {byQuadrant.keep_satisfied.map((s) => (
                <div key={s.id} className="p-2 bg-white rounded border border-orange-200">
                  <p className="font-medium text-sm">{s.name}</p>
                  <p className="text-xs text-muted-foreground">{s.role}</p>
                </div>
              ))}
              {byQuadrant.keep_satisfied.length === 0 && (
                <p className="text-xs text-muted-foreground italic">No stakeholders</p>
              )}
            </div>
          </div>

          {/* Keep Informed (Low Power, High Interest) */}
          <div className="p-4 border-2 border-blue-200 bg-blue-50 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 rounded-full bg-blue-500" />
              <span className="font-medium text-blue-800">Keep Informed</span>
            </div>
            <p className="text-xs text-blue-600 mb-3">Low Power, High Interest</p>
            <div className="space-y-2">
              {byQuadrant.keep_informed.map((s) => (
                <div key={s.id} className="p-2 bg-white rounded border border-blue-200">
                  <p className="font-medium text-sm">{s.name}</p>
                  <p className="text-xs text-muted-foreground">{s.role}</p>
                </div>
              ))}
              {byQuadrant.keep_informed.length === 0 && (
                <p className="text-xs text-muted-foreground italic">No stakeholders</p>
              )}
            </div>
          </div>

          {/* Monitor (Low Power, Low Interest) */}
          <div className="p-4 border-2 border-gray-200 bg-gray-50 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 rounded-full bg-gray-500" />
              <span className="font-medium text-gray-800">Monitor</span>
            </div>
            <p className="text-xs text-gray-600 mb-3">Low Power, Low Interest</p>
            <div className="space-y-2">
              {byQuadrant.monitor.map((s) => (
                <div key={s.id} className="p-2 bg-white rounded border border-gray-200">
                  <p className="font-medium text-sm">{s.name}</p>
                  <p className="text-xs text-muted-foreground">{s.role}</p>
                </div>
              ))}
              {byQuadrant.monitor.length === 0 && (
                <p className="text-xs text-muted-foreground italic">No stakeholders</p>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Stakeholder List */}
      <div className="space-y-3">
        <h2 className="font-semibold text-foreground">All Stakeholders</h2>
        {stakeholders.map((stakeholder) => {
          const quadrantInfo = getQuadrantInfo(stakeholder.quadrant);

          return (
            <Card key={stakeholder.id} className="p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start gap-4">
                {/* Avatar */}
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-slate-200 to-slate-300 flex items-center justify-center">
                  <Users className="w-6 h-6 text-slate-600" />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold text-foreground">
                      {stakeholder.name}
                    </h3>
                    <Badge
                      className="text-xs"
                      style={{ backgroundColor: quadrantInfo.color }}
                    >
                      {quadrantInfo.label}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-4 text-sm text-muted-foreground mb-2">
                    <span className="flex items-center gap-1">
                      <Briefcase className="w-3 h-3" />
                      {stakeholder.role}
                    </span>
                    <span className="flex items-center gap-1">
                      <Building2 className="w-3 h-3" />
                      {stakeholder.organization}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {getPowerBadge(stakeholder.power_level)}
                    {getInterestBadge(stakeholder.interest_level)}
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
