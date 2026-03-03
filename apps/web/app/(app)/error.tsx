'use client';

import { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[AppError]', error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="rounded-full bg-destructive/10 p-4">
        <AlertTriangle className="h-8 w-8 text-destructive" />
      </div>
      <h2 className="mt-4 text-lg font-semibold text-foreground">
        Something went wrong
      </h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        {error.message || 'An unexpected error occurred while loading this page.'}
      </p>
      {error.digest ? (
        <p className="mt-1 font-mono text-xs text-muted-foreground">
          Error ID: {error.digest}
        </p>
      ) : null}
      <Button onClick={reset} variant="outline" className="mt-6">
        Try again
      </Button>
    </div>
  );
}
