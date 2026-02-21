"use client";

import { useEffect } from "react";
import { LayoutErrorState } from "@/components/layout/LayoutErrorState";

export default function AppSectionError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[app layout error boundary]", error);
  }, [error]);

  return (
    <LayoutErrorState
      title="No pudimos cargar esta sección"
      description="Ocurrió un problema inesperado al renderizar el contenido de la aplicación."
      retryLabel="Volver a intentar"
      details={error.message}
      onRetry={reset}
    />
  );
}
