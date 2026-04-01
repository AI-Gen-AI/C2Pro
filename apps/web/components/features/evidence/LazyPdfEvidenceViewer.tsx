/**
 * Test Suite ID: S3-01
 * Backlog Task: TASK-023
 */
"use client";

import dynamic from "next/dynamic";
import type { ComponentProps } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import type { PdfEvidenceViewer } from "./PdfEvidenceViewer";

type PdfEvidenceViewerProps = ComponentProps<typeof PdfEvidenceViewer>;

const LazyPdfEvidenceViewer = dynamic<PdfEvidenceViewerProps>(
  () =>
    import("./PdfEvidenceViewer").then((module) => module.PdfEvidenceViewer),
  {
    ssr: false,
    loading: () => (
      <div
        data-testid="pdf-evidence-viewer-loading"
        className="flex h-[70vh] items-center justify-center rounded-lg border bg-background/60"
      >
        <div className="w-full max-w-3xl space-y-3 px-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-[60vh] w-full" />
        </div>
      </div>
    ),
  },
);

export { LazyPdfEvidenceViewer };
