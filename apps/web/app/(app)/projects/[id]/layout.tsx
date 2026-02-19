import type { ReactNode } from "react";
import { ProjectTabs } from "@/components/layout/ProjectTabs";

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
      <div className="rounded-md border bg-card p-4">
        <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
          Project
        </div>
        <h2 className="text-lg font-semibold">{id}</h2>
        <ProjectTabs projectId={id} />
      </div>
      {children}
    </section>
  );
}
