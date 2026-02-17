"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Search, BarChart3 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Input } from "@/components/ui/input";

export default function ProjectsPage() {
  const [searchQuery, setSearchQuery] = useState("");

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              C2Pro Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Welcome, Project Manager
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Button className="gap-2" data-testid="new-project-button">
              <Plus className="w-4 h-4" />
              New Project
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Welcome Card */}
        <Card className="mb-8 bg-gradient-to-r from-primary/10 to-primary/5 border-primary/20">
          <CardHeader>
            <CardTitle className="text-lg">Get Started with C2Pro</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Upload your construction project documents to start analyzing
              contract coherence across Scope, Budget, Quality, Technical,
              Legal, and Time dimensions.
            </p>
            <Button className="w-full sm:w-auto">
              <BarChart3 className="mr-2 w-4 h-4" />
              Upload Your First Project
            </Button>
          </CardContent>
        </Card>

        {/* Projects Section */}
        <div className="space-y-4" data-testid="projects-list">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-foreground">Your Projects</h2>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search your projects..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Mock Project for E2E Testing */}
          <Link href="/dashboard/projects/test-project-id/dashboard">
            <Card
              className="cursor-pointer hover:border-primary/50 transition-colors"
              data-testid="project-card-1"
            >
              <CardHeader>
                <CardTitle>Torre Skyline Office Building</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>Status: In Progress</span>
                  <span>•</span>
                  <span>Completion: 65%</span>
                </div>
              </CardContent>
            </Card>
          </Link>
        </div>
      </main>
    </div>
  );
}
