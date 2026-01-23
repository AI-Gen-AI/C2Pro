import Link from "next/link";
import type { ReactNode } from "react";

export default function ProjectLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  return (
    <section className="space-y-6">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Proyecto
        </p>
        <h2 className="text-xl font-semibold">{params.id}</h2>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <Link
            href={`/projects/${params.id}`}
            className="rounded-md border border-border px-3 py-1 transition hover:bg-accent"
          >
            Overview
          </Link>
          <Link
            href={`/projects/${params.id}/evidence`}
            className="rounded-md border border-border px-3 py-1 transition hover:bg-accent"
          >
            Evidence
          </Link>
          <Link
            href={`/projects/${params.id}/analysis`}
            className="rounded-md border border-border px-3 py-1 transition hover:bg-accent"
          >
            Alerts
          </Link>
        </div>
      </div>
      {children}
    </section>
  );
}
