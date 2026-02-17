"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Upload, FileText, ChevronRight, ChevronLeft } from "lucide-react";

type Step = "info" | "contract" | "clauses" | "wbs" | "review";

export default function NewProjectPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const stepParam = searchParams.get("step") as Step | null;

  const [currentStep, setCurrentStep] = useState<Step>(stepParam || "info");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);

  // Form data
  const [formData, setFormData] = useState({
    name: "",
    client: "",
    description: "",
    startDate: "",
    endDate: "",
    currency: "EUR",
  });

  const steps: { id: Step; label: string }[] = [
    { id: "info", label: "Project Info" },
    { id: "contract", label: "Contract" },
    { id: "clauses", label: "Clauses" },
    { id: "wbs", label: "WBS" },
    { id: "review", label: "Review" },
  ];

  const handleNext = () => {
    const currentIndex = steps.findIndex((s) => s.id === currentStep);
    if (currentIndex < steps.length - 1) {
      const nextStep = steps[currentIndex + 1].id;
      setCurrentStep(nextStep);
      router.push(`/projects/new?step=${nextStep}`);
    }
  };

  const handleBack = () => {
    const currentIndex = steps.findIndex((s) => s.id === currentStep);
    if (currentIndex > 0) {
      const prevStep = steps[currentIndex - 1].id;
      setCurrentStep(prevStep);
      router.push(`/projects/new?step=${prevStep}`);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(0);

    // Simulate upload progress
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 10;
      });
    }, 200);

    // Simulate upload completion
    setTimeout(() => {
      setIsUploading(false);
      setUploadedFile(file.name);
      setIsExtracting(true);

      // Simulate extraction
      setTimeout(() => {
        setIsExtracting(false);
        handleNext();
      }, 2000);
    }, 2000);
  };

  const handleCreateProject = () => {
    // Navigate to project dashboard
    router.push("/dashboard/projects/test-project-id");
  };

  const currentStepIndex = steps.findIndex((s) => s.id === currentStep);
  const progress = ((currentStepIndex + 1) / steps.length) * 100;

  return (
    <div className="mx-auto max-w-4xl space-y-6" data-testid="project-creation-form">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">Create New Project</h1>
        <p className="text-muted-foreground">
          Set up your project by providing basic information and uploading your contract documents.
        </p>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>Step {currentStepIndex + 1} of {steps.length}</span>
          <span>{steps[currentStepIndex]?.label}</span>
        </div>
        <Progress value={progress} className="h-2" />
      </div>

      {/* Step Content */}
      <Card>
        <CardHeader>
          <CardTitle>{steps[currentStepIndex]?.label}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Step 1: Project Info */}
          {currentStep === "info" && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="project-name">Project Name</Label>
                <Input
                  id="project-name"
                  data-testid="project-name-input"
                  placeholder="e.g., Commercial Building Renovation"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="client-name">Client Name</Label>
                <Input
                  id="client-name"
                  data-testid="client-name-input"
                  placeholder="e.g., ABC Construction Corp"
                  value={formData.client}
                  onChange={(e) =>
                    setFormData({ ...formData, client: e.target.value })
                  }
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
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="start-date">Start Date</Label>
                  <Input
                    id="start-date"
                    data-testid="start-date-input"
                    type="date"
                    value={formData.startDate}
                    onChange={(e) =>
                      setFormData({ ...formData, startDate: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="end-date">End Date</Label>
                  <Input
                    id="end-date"
                    data-testid="end-date-input"
                    type="date"
                    value={formData.endDate}
                    onChange={(e) =>
                      setFormData({ ...formData, endDate: e.target.value })
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="currency">Currency</Label>
                <Select
                  value={formData.currency}
                  onValueChange={(value) =>
                    setFormData({ ...formData, currency: value })
                  }
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
            </div>
          )}

          {/* Step 2: Contract Upload */}
          {currentStep === "contract" && (
            <div className="space-y-6" data-testid="contract-upload-step">
              {!isUploading && !isExtracting && !uploadedFile && (
                <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/25 p-12">
                  <Upload className="mb-4 h-12 w-12 text-muted-foreground" />
                  <p className="mb-2 text-lg font-medium">Upload Contract Document</p>
                  <p className="mb-4 text-sm text-muted-foreground">
                    Drag and drop your PDF contract, or click to browse
                  </p>
                  <Input
                    type="file"
                    accept=".pdf"
                    data-testid="contract-file-input"
                    onChange={handleFileUpload}
                    className="hidden"
                    id="contract-upload"
                  />
                  <Button asChild>
                    <label htmlFor="contract-upload">Select File</label>
                  </Button>
                </div>
              )}

              {isUploading && (
                <div className="space-y-4" data-testid="upload-progress">
                  <p className="text-center font-medium">Uploading document...</p>
                  <Progress value={uploadProgress} className="h-2" />
                  <p className="text-center text-sm text-muted-foreground">
                    {uploadProgress}%
                  </p>
                </div>
              )}

              {uploadedFile && !isExtracting && (
                <div className="space-y-4" data-testid="upload-complete">
                  <div className="flex items-center gap-3 rounded-lg bg-muted p-4">
                    <FileText className="h-8 w-8 text-primary" />
                    <div>
                      <p className="font-medium">{uploadedFile}</p>
                      <p className="text-sm text-muted-foreground">
                        Upload complete
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {isExtracting && (
                <div className="space-y-4" data-testid="extraction-progress">
                  <p className="text-center font-medium">AI is analyzing your contract...</p>
                  <Progress value={45} className="h-2" />
                  <p className="text-center text-sm text-muted-foreground">
                    Extracting clauses and key terms
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Clauses */}
          {currentStep === "clauses" && (
            <div className="space-y-4" data-testid="extracted-clauses-section">
              <div className="rounded-lg bg-muted p-4">
                <p className="text-sm text-muted-foreground">
                  AI has extracted the following clauses from your contract. Review and edit as needed.
                </p>
              </div>

              <div className="space-y-4" data-testid="scope-clauses">
                <h3 className="font-semibold">Scope of Work</h3>
                <div className="rounded-lg border p-4">
                  <p className="text-sm">Complete renovation of 5-story commercial building including HVAC, electrical, and structural updates.</p>
                </div>
              </div>

              <div className="space-y-4" data-testid="budget-clauses">
                <h3 className="font-semibold">Payment Terms</h3>
                <div className="rounded-lg border p-4">
                  <p className="text-sm">Total contract value: €2,500,000. Payment schedule: 30% upfront, 40% at midpoint, 30% upon completion.</p>
                </div>
              </div>

              <div className="space-y-4" data-testid="timeline-clauses">
                <h3 className="font-semibold">Project Schedule</h3>
                <div className="rounded-lg border p-4">
                  <p className="text-sm">Project duration: 7 months. Start date: June 1, 2025. Completion deadline: December 31, 2025.</p>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg bg-primary/10 p-4" data-testid="extraction-confidence">
                <span className="text-sm font-medium">Extraction Confidence</span>
                <span className="text-lg font-bold text-primary">94%</span>
              </div>
            </div>
          )}

          {/* Step 4: WBS Generation */}
          {currentStep === "wbs" && (
            <div className="space-y-4" data-testid="wbs-generation-preview">
              <p className="text-sm text-muted-foreground">
                Based on the extracted clauses, we&apos;ve generated an initial WBS structure.
              </p>

              <div className="space-y-2" data-testid="wbs-tree">
                <div className="rounded-lg border p-3" data-testid="wbs-item-code-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">1 - Project Management</span>
                    <span className="text-sm text-muted-foreground">15%</span>
                  </div>
                </div>
                <div className="rounded-lg border p-3" data-testid="wbs-item-code-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">2 - Construction</span>
                    <span className="text-sm text-muted-foreground">45%</span>
                  </div>
                </div>
                <div className="rounded-lg border p-3" data-testid="wbs-item-code-1.1">
                  <div className="flex items-center justify-between pl-6">
                    <span>1.1 - Planning</span>
                    <span className="text-sm text-muted-foreground">5%</span>
                  </div>
                </div>
              </div>

              <p className="text-center text-sm text-muted-foreground" data-testid="wbs-item-count">
                8 items generated
              </p>
            </div>
          )}

          {/* Step 5: Review */}
          {currentStep === "review" && (
            <div className="space-y-6" data-testid="project-summary">
              <div className="space-y-4">
                <h3 className="font-semibold">Project Details</h3>
                <div className="rounded-lg bg-muted p-4">
                  <p className="font-medium">{formData.name || "Commercial Building Renovation"}</p>
                  <p className="text-sm text-muted-foreground">{formData.client || "ABC Construction Corp"}</p>
                </div>
              </div>

              <div className="space-y-4" data-testid="wbs-summary">
                <h3 className="font-semibold">WBS Structure</h3>
                <div className="rounded-lg bg-muted p-4">
                  <p className="text-sm">8 WBS items generated from contract</p>
                </div>
              </div>

              <Button
                size="lg"
                className="w-full"
                data-testid="create-project-button"
                onClick={handleCreateProject}
              >
                Create Project
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={currentStepIndex === 0}
          className="gap-2"
        >
          <ChevronLeft className="h-4 w-4" />
          Back
        </Button>

        {currentStep !== "review" && (
          <Button
            onClick={handleNext}
            disabled={currentStep === "contract" && (!uploadedFile || isUploading || isExtracting)}
            className="gap-2"
            data-testid="project-info-next-button"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  );
}
