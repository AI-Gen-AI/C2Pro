"use client";

import { useSearchParams } from "next/navigation";
import { StakeholderMatrix } from "@/components/stakeholders/StakeholderMatrix";

export default function StakeholdersPage() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId") ?? undefined;

  return (
    <section className="space-y-6">
      <StakeholderMatrix projectId={projectId} />
      {!projectId ? (
        <p className="text-sm text-muted-foreground">
          Agrega ?projectId=UUID a la URL para cargar stakeholders del proyecto.
        </p>
      ) : null}
    </section>
  );
}
