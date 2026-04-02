import type { ReactNode } from "react";
import { ProjectHeaderCard } from "@/components/layout/ProjectHeaderCard";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <section className="space-y-5">
      <ProjectHeaderCard projectId={id} />
      {children}
    </section>
  );
}
