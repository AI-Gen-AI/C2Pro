"use client";

import { useEffect } from "react";
import { LayoutErrorState } from "@/components/layout/LayoutErrorState";

export default function ProjectLayoutError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[project layout error boundary]", error);
  }, [error]);

  return (
    <LayoutErrorState
      title="Error al cargar el proyecto"
      description="No se pudo renderizar esta vista del proyecto."
      retryLabel="Reintentar carga"
      details={error.message}
      onRetry={reset}
    />
  );
}
