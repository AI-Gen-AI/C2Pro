"use client";

import { useTheme } from "next-themes";

interface ThemeToggleProps {
  className?: string;
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      aria-label="Toggle dark mode"
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className={`inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-card text-primary-text transition hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${className ?? ""}`}
    >
      <span className="sr-only">Toggle dark mode</span>
      <span aria-hidden className="text-xs font-semibold">
        {isDark ? "D" : "L"}
      </span>
    </button>
  );
}
