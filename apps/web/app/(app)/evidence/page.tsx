'use client';

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { FileSearch, ArrowRight } from 'lucide-react';

export default function EvidencePage() {
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
          Evidence review is now organized by project. Select a project to view and analyze its documents,
          extracted data, and approve or reject findings.
        </p>
        <div className="flex flex-col gap-2 pt-4">
          <Button onClick={() => router.push('/projects')}>
            <ArrowRight className="mr-2 h-4 w-4" />
            Go to Projects
          </Button>
          <Button variant="outline" onClick={() => router.push('/documents')}>
            View All Documents
          </Button>
        </div>
      </div>
    </div>
  );
}
