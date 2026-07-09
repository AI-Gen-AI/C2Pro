/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy } from "../copy";
import { Eyebrow, H2, SectionShell } from "../primitives";

type HowItWorksProps = {
  copy: LandingCopy["howItWorks"];
};

export function HowItWorks({ copy }: HowItWorksProps) {
  return (
    <SectionShell id="como-funciona" variant="paper">
      <div className="max-w-3xl">
        <Eyebrow>{copy.eyebrow}</Eyebrow>
        <H2 className="mt-4">{copy.h2}</H2>
        <p className="mt-5 text-lg leading-8 text-brand-slate">{copy.lead}</p>
      </div>
      <div className="mt-10 grid gap-4 md:grid-cols-4">
        {copy.steps.map((step) => (
          <article
            className="rounded-[14px] border border-brand-line bg-brand-paper p-5"
            key={step.number}
          >
            <div className="font-mono text-sm text-brand-accent-ink">
              {step.number}
            </div>
            <h3 className="mt-4 font-semibold text-brand-ink">{step.title}</h3>
            <p className="mt-3 text-sm leading-6 text-brand-slate">{step.text}</p>
          </article>
        ))}
      </div>
    </SectionShell>
  );
}
