"use client";

import { useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  AlertTriangle,
  Users,
  Calendar,
  TrendingUp,
  Eye,
} from "lucide-react";
import { SAMPLE_DATA } from "@/contexts/demo-mode";

function getScoreColor(score: number) {
  if (score >= 80) return "text-green-600 bg-green-100";
  if (score >= 60) return "text-yellow-600 bg-yellow-100";
  return "text-red-600 bg-red-100";
}

function getStatusBadge(status: string) {
  switch (status) {
    case "active":
      return <Badge className="bg-green-100 text-green-700">Active</Badge>;
    case "draft":
      return <Badge className="bg-gray-100 text-gray-700">Draft</Badge>;
    case "completed":
      return <Badge className="bg-blue-100 text-blue-700">Completed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export default function DemoProjectsPage() {
  const projects = SAMPLE_DATA.projects;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Projects</h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">
            {projects.length} projects
          </span>
          <Button disabled className="opacity-50 cursor-not-allowed">
            + New Project
          </Button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-sm text-blue-800">
          This is a demo workspace with sample data. Sign in to create your own projects.
        </p>
      </div>

      {/* Projects Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Card key={project.id} className="p-5 hover:shadow-md transition-shadow">
            <div className="space-y-4">
              {/* Header */}
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-foreground truncate">
                    {project.name}
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                    {project.description}
                  </p>
                </div>
                {getStatusBadge(project.status)}
              </div>

              {/* Coherence Score */}
              <div className="flex items-center gap-3">
                <div
                  className={`flex items-center justify-center w-12 h-12 rounded-lg font-bold text-lg ${getScoreColor(
                    project.coherence_score
                  )}`}
                >
                  {project.coherence_score}
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">
                    Coherence Score
                  </div>
                  <div className="flex items-center gap-1 text-xs text-green-600">
                    <TrendingUp className="w-3 h-3" />
                    <span>+3 this week</span>
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-4 gap-2 pt-3 border-t">
                <div className="text-center">
                  <FileText className="w-4 h-4 mx-auto text-muted-foreground" />
                  <div className="text-sm font-medium mt-1">
                    {project.document_count}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Docs</div>
                </div>
                <div className="text-center">
                  <AlertTriangle className="w-4 h-4 mx-auto text-muted-foreground" />
                  <div className="text-sm font-medium mt-1">
                    {project.alert_count}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Alerts</div>
                </div>
                <div className="text-center">
                  <Users className="w-4 h-4 mx-auto text-muted-foreground" />
                  <div className="text-sm font-medium mt-1">
                    {project.stakeholder_count}
                  </div>
                  <div className="text-[10px] text-muted-foreground">People</div>
                </div>
                <div className="text-center">
                  <Calendar className="w-4 h-4 mx-auto text-muted-foreground" />
                  <div className="text-sm font-medium mt-1">
                    {project.clause_count}
                  </div>
                  <div className="text-[10px] text-muted-foreground">Clauses</div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Link href={`/demo/projects/${project.id}`} className="flex-1">
                  <Button variant="outline" size="sm" className="w-full">
                    <Eye className="w-4 h-4 mr-2" />
                    View Details
                  </Button>
                </Link>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
