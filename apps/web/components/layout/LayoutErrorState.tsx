"use client";

import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";

type LayoutErrorStateProps = {
  title: string;
  description: string;
  retryLabel?: string;
  onRetry: () => void;
  details?: string;
  icon?: ReactNode;
};

export function LayoutErrorState({
  title,
  description,
  retryLabel = "Reintentar",
  onRetry,
  details,
  icon,
}: LayoutErrorStateProps) {
  return (
    <div className="mx-auto flex min-h-[55vh] max-w-2xl flex-col items-center justify-center rounded-xl border bg-card px-6 py-10 text-center shadow-sm">
      <div className="mb-4 rounded-full bg-destructive/10 p-3 text-destructive">
        {icon ?? <AlertTriangle className="h-6 w-6" aria-hidden="true" />}
      </div>
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      <p className="mt-2 max-w-xl text-sm text-muted-foreground">{description}</p>
      {details ? (
        <p className="mt-2 max-w-xl text-xs text-muted-foreground/80">{details}</p>
      ) : null}
      <Button type="button" className="mt-6" onClick={onRetry}>
        {retryLabel}
      </Button>
    </div>
  );
}
