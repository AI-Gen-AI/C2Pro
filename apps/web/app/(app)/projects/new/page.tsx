"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";

export default function NewProjectPage() {
  const router = useRouter();
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: "",
    code: "",
    client: "",
    description: "",
    currency: "EUR",
  });

  const handleCreateProject = async () => {
    if (!formData.name.trim()) {
      setCreateError("Project name is required");
      return;
    }

    setIsCreating(true);
    setCreateError(null);

    try {
      const response = await apiClient.post("/projects", {
        name: formData.name,
        code: formData.code || undefined,
        description: formData.description || undefined,
        client_name: formData.client || undefined,
        currency: formData.currency,
      });

      const project = response.data;
      // Navigate to the new project's documents page to upload contracts
      router.push(`/projects/${project.id}/documents`);
    } catch (error: any) {
      console.error("Failed to create project:", error);
      const message = error?.response?.data?.detail || error?.message || "Failed to create project";
      setCreateError(message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <Button variant="ghost" size="sm" asChild className="mb-2">
          <Link href="/projects">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Projects
          </Link>
        </Button>
        <h1 className="text-2xl font-bold">Create New Project</h1>
        <p className="text-muted-foreground">
          Enter your project details. You can upload contracts and documents after creation.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Project Information</CardTitle>
          <CardDescription>
            Basic details about your project
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="project-name">Project Name *</Label>
            <Input
              id="project-name"
              data-testid="project-name-input"
              placeholder="e.g., Edificio Central - Fase 1"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="project-code">Project Code</Label>
            <Input
              id="project-code"
              data-testid="project-code-input"
              placeholder="e.g., EDIF-001"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value })}
            />
            <p className="text-xs text-muted-foreground">
              Optional unique identifier for your project
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="client-name">Client Name</Label>
            <Input
              id="client-name"
              data-testid="client-name-input"
              placeholder="e.g., Constructora ABC S.L."
              value={formData.client}
              onChange={(e) => setFormData({ ...formData, client: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Project Description</Label>
            <Textarea
              id="description"
              data-testid="project-description-input"
              placeholder="Describe the project scope, objectives, and key deliverables..."
              rows={4}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="currency">Currency</Label>
            <Select
              value={formData.currency}
              onValueChange={(value) => setFormData({ ...formData, currency: value })}
            >
              <SelectTrigger id="currency" data-testid="currency-select">
                <SelectValue placeholder="Select currency" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="EUR">EUR (€)</SelectItem>
                <SelectItem value="USD">USD ($)</SelectItem>
                <SelectItem value="GBP">GBP (£)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {createError && (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              {createError}
            </div>
          )}

          <div className="flex gap-4 pt-4">
            <Button variant="outline" asChild className="flex-1">
              <Link href="/projects">Cancel</Link>
            </Button>
            <Button
              className="flex-1"
              data-testid="create-project-button"
              onClick={handleCreateProject}
              disabled={isCreating || !formData.name.trim()}
            >
              {isCreating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                "Create Project"
              )}
            </Button>
          </div>

          <p className="text-center text-sm text-muted-foreground">
            After creating the project, you'll be redirected to upload documents.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
