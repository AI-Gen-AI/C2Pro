import Link from "next/link";

const navItems = [
  { label: "Dashboard", href: "/" },
  { label: "Projects", href: "/projects" },
  { label: "Create Project", href: "/projects/new" },
];

export default function Sidebar() {
  return (
    <aside className="min-h-screen w-64 border-r border-border bg-card px-4 py-6">
      <div className="mb-8">
        <div className="text-lg font-semibold">C2Pro</div>
        <div className="text-xs text-muted-foreground">Enterprise SaaS</div>
      </div>
      <nav className="space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className="block rounded-md px-3 py-2 text-sm text-foreground transition hover:bg-accent"
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="mt-8 rounded-md border border-border bg-muted p-3 text-xs text-muted-foreground">
        Modulos listos para Evidence, Alerts y Stakeholders.
      </div>
    </aside>
  );
}
