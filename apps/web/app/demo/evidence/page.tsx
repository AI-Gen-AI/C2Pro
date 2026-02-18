"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { FileSearch, ArrowRight } from "lucide-react";

export default function DemoEvidencePage() {
  const router = useRouter();

  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center space-y-4 max-w-md">
        <div className="flex justify-center">
          <div className="rounded-full bg-primary/10 p-6">
            <FileSearch className="h-12 w-12 text-primary" />
          </div>
        </div>
        <h2 className="text-2xl font-bold">Evidence Review</h2>
        <p className="text-muted-foreground">
          Evidence review is organized by project. Select a project to view and
          analyze its documents, extracted data, and approve or reject findings.
        </p>
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            This is a demo feature. Sign in to access full evidence review
            capabilities.
          </p>
        </div>
        <div className="flex flex-col gap-2 pt-4">
          <Button onClick={() => router.push("/demo/projects")}>
            <ArrowRight className="mr-2 h-4 w-4" />
            View Demo Projects
          </Button>
          <Button variant="outline" onClick={() => router.push("/demo/documents")}>
            View Demo Documents
          </Button>
        </div>
      </div>
    </div>
  );
}
