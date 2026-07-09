/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import Link from "next/link";
import type { LandingCopy } from "../copy";

type LandingFooterProps = {
  copy: LandingCopy["footer"];
};

function isExternal(href: string) {
  return href.startsWith("https://");
}

function isAnchorLike(href: string) {
  return href.startsWith("mailto:") || href.startsWith("#");
}

function FooterLink({ href, label }: { href: string; label: string }) {
  if (isExternal(href)) {
    return (
      <a className="text-brand-on-navy-muted hover:text-brand-on-navy" href={href} rel="noopener">
        {label}
      </a>
    );
  }

  if (isAnchorLike(href)) {
    return (
      <a className="text-brand-on-navy-muted hover:text-brand-on-navy" href={href}>
        {label}
      </a>
    );
  }

  return (
    <Link className="text-brand-on-navy-muted hover:text-brand-on-navy" href={href}>
      {label}
    </Link>
  );
}

export function LandingFooter({ copy }: LandingFooterProps) {
  return (
    <footer className="bg-brand-navy-2 px-6 py-12 text-brand-on-navy">
      <div className="mx-auto max-w-[1200px]">
        <div className="grid gap-10 lg:grid-cols-[1.2fr_2fr]">
          <div>
            <div className="font-brand-display text-3xl font-medium">C2Pro</div>
            <p className="mt-3 text-brand-on-navy-muted">{copy.tagline}</p>
            <a
              className="mt-5 inline-block text-brand-accent-on-navy underline underline-offset-4"
              href={copy.ecosystem.href}
              rel="noopener"
            >
              {copy.ecosystem.text}
            </a>
          </div>
          <div className="grid gap-8 sm:grid-cols-3">
            {copy.columns.map((column) => (
              <div key={column.title}>
                <h3 className="font-mono text-xs uppercase tracking-[0.18em] text-brand-accent-on-navy">
                  {column.title}
                </h3>
                <div className="mt-4 grid gap-3 text-sm">
                  {column.links.map((link) => (
                    <FooterLink href={link.href} key={link.label} label={link.label} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-10 flex flex-col gap-4 border-t border-brand-on-navy-muted/20 pt-6 text-sm text-brand-on-navy-muted md:flex-row md:items-center md:justify-between">
          <div>{copy.bottom}</div>
          <div className="flex flex-wrap gap-4">
            {copy.legal.map((link) => (
              <FooterLink href={link.href} key={link.label} label={link.label} />
            ))}
            <FooterLink href={copy.localeSwitch.href} label={copy.localeSwitch.label} />
          </div>
        </div>
      </div>
    </footer>
  );
}
