"use client";

/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import type { LandingCopy, LandingLocale } from "../copy";
import { LandingAuthButtons } from "../landing-auth-buttons";
import { cn } from "@/lib/utils";

type LandingHeaderProps = Readonly<{
  copy: LandingCopy["header"];
  locale: LandingLocale;
}>;

export function LandingHeader({ copy, locale }: LandingHeaderProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const labels = {
    signIn: copy.signIn,
    joinPilot: copy.cta,
    workspace: copy.workspace,
  };

  return (
    <header className="sticky top-0 z-50 border-b border-brand-line-soft bg-brand-alabaster/95 backdrop-blur">
      <div className="mx-auto flex h-20 max-w-[1200px] items-center justify-between px-6">
        <Link
          className="font-brand-display text-2xl font-medium tracking-normal text-brand-ink"
          href={locale === "es" ? "/" : "/en"}
        >
          C2Pro
        </Link>
        <a
          className="hidden font-mono text-[0.7rem] uppercase tracking-[0.16em] text-brand-muted hover:text-brand-accent-ink md:inline"
          href="https://www.ai-gen.ai"
          rel="noopener"
        >
          · {copy.microTag}
        </a>
        <nav aria-label="Principal" className="hidden items-center gap-7 md:flex">
          {copy.nav.map((item) => (
            <a
              className="text-sm text-brand-slate hover:text-brand-accent-ink"
              href={item.href}
              key={item.href}
            >
              {item.label}
            </a>
          ))}
          <Link
            className="font-mono text-xs uppercase tracking-[0.16em] text-brand-muted hover:text-brand-accent-ink"
            href={copy.localeSwitch.href}
          >
            {copy.localeSwitch.label}
          </Link>
        </nav>
        <div className="hidden md:block">
          <LandingAuthButtons labels={labels} />
        </div>
        <button
          aria-expanded={open}
          aria-label="Menu"
          className="inline-flex h-10 w-10 items-center justify-center rounded-[14px] border border-brand-line text-brand-ink md:hidden"
          onClick={() => setOpen((value) => !value)}
          type="button"
        >
          <span className="sr-only">Menu</span>
          <span className={cn("block h-0.5 w-5 bg-current", open && "rotate-45")} />
        </button>
      </div>
      {open ? (
        <div
          aria-label="Menu"
          className="fixed inset-x-0 top-20 z-50 border-b border-brand-line bg-brand-alabaster px-6 py-6 shadow-lg md:hidden"
          role="dialog"
        >
          <div className="mb-6 flex items-center justify-between">
            <span className="font-brand-display text-xl font-medium">C2Pro</span>
            <button
              aria-label="Close menu"
              className="rounded-[14px] border border-brand-line px-3 py-2 text-sm"
              onClick={() => setOpen(false)}
              type="button"
            >
              ×
            </button>
          </div>
          <nav aria-label="Principal mobile" className="grid gap-4">
            {copy.nav.map((item) => (
              <a
                className="text-lg text-brand-ink"
                href={item.href}
                key={item.href}
                onClick={() => setOpen(false)}
              >
                {item.label}
              </a>
            ))}
            <Link href={copy.localeSwitch.href}>{copy.localeSwitch.label}</Link>
          </nav>
          <div className="mt-6">
            <LandingAuthButtons labels={labels} />
          </div>
        </div>
      ) : null}
    </header>
  );
}
