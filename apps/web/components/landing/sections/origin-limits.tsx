/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy } from "../copy";
import { SectionIntro, SectionShell } from "../primitives";

type OriginLimitsProps = {
  copy: LandingCopy["originLimits"];
};

export function OriginLimits({ copy }: OriginLimitsProps) {
  return (
    <SectionShell id="origen" variant="alabaster">
      <SectionIntro
        eyebrow={copy.eyebrow}
        heading={copy.h2}
        headingClassName="max-w-3xl"
      />
      <div className="mt-10 grid gap-6 md:grid-cols-2">
        <article className="rounded-[14px] border border-brand-line bg-brand-paper p-6">
          <h3 className="text-lg font-semibold text-brand-ink">
            {copy.ecosystem.h3}
          </h3>
          <p className="mt-4 leading-7 text-brand-slate">
            {copy.ecosystem.textBeforeLink}
            <a
              className="text-brand-accent-ink underline underline-offset-4"
              href={copy.ecosystem.link.href}
              rel="noopener"
            >
              {copy.ecosystem.link.text}
            </a>
            {copy.ecosystem.textAfterLink}
          </p>
        </article>
        <article className="rounded-[14px] border border-brand-line bg-brand-paper p-6">
          <h3 className="text-lg font-semibold text-brand-ink">{copy.limits.h3}</h3>
          <p className="mt-4 leading-7 text-brand-slate">{copy.limits.text}</p>
        </article>
      </div>
    </SectionShell>
  );
}
