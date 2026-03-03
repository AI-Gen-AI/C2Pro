"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, AlertCircle, Info, CheckCircle } from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";

function getSeverityConfig(severity: string) {
  switch (severity) {
    case "critical":
      return {
        icon: AlertTriangle,
        color: "text-red-600",
        bg: "bg-red-50 border-red-200",
        badge: "bg-red-100 text-red-700",
      };
    case "high":
      return {
        icon: AlertCircle,
        color: "text-orange-600",
        bg: "bg-orange-50 border-orange-200",
        badge: "bg-orange-100 text-orange-700",
      };
    case "medium":
      return {
        icon: Info,
        color: "text-yellow-600",
        bg: "bg-yellow-50 border-yellow-200",
        badge: "bg-yellow-100 text-yellow-700",
      };
    default:
      return {
        icon: CheckCircle,
        color: "text-blue-600",
        bg: "bg-blue-50 border-blue-200",
        badge: "bg-blue-100 text-blue-700",
      };
  }
}

function getStatusBadge(status: string) {
  switch (status) {
    case "open":
      return <Badge className="bg-red-100 text-red-700">Open</Badge>;
    case "resolved":
      return <Badge className="bg-green-100 text-green-700">Resolved</Badge>;
    case "dismissed":
      return <Badge className="bg-gray-100 text-gray-700">Dismissed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function DemoAlertsPage() {
  const alerts = SAMPLE_DATA.alerts;
  const openAlerts = alerts.filter((a) => a.status === "open");
  const criticalCount = alerts.filter((a) => a.severity === "critical").length;
  const highCount = alerts.filter((a) => a.severity === "high").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Alerts</h1>
          <p className="text-sm text-muted-foreground">
            Contract coherence alerts and issues
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {openAlerts.length} open
            </span>
            {criticalCount > 0 && (
              <Badge className="bg-red-100 text-red-700">
                {criticalCount} critical
              </Badge>
            )}
            {highCount > 0 && (
              <Badge className="bg-orange-100 text-orange-700">
                {highCount} high
              </Badge>
            )}
          </div>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          Demo alerts showing sample contract coherence issues. Sign in to analyze your own documents.
        </p>
      </div>

      {/* Alerts List */}
      <div className="space-y-3">
        {alerts.map((alert) => {
          const config = getSeverityConfig(alert.severity);
          const Icon = config.icon;

          return (
            <Card
              key={alert.id}
              className={`p-4 border ${config.bg} transition-shadow hover:shadow-md`}
            >
              <div className="flex items-start gap-4">
                <div className={`mt-0.5 ${config.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={config.badge}>
                      {alert.severity.toUpperCase()}
                    </Badge>
                    {getStatusBadge(alert.status)}
                    <span className="text-xs text-muted-foreground">
                      {alert.type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-foreground">
                    {alert.message}
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>Affected: {alert.affected_entity}</span>
                    <span>
                      {new Date(alert.created_at).toLocaleDateString()}
                    </span>
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
