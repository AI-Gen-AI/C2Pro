/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy } from "../copy";
import { SectionIntro, SectionShell } from "../primitives";

type DimensionsProps = Readonly<{
  copy: LandingCopy["dimensions"];
}>;

export function Dimensions({ copy }: DimensionsProps) {
  return (
    <SectionShell id="producto" variant="paper">
      <SectionIntro
        className="max-w-3xl"
        eyebrow={copy.eyebrow}
        heading={copy.h2}
        body={copy.prose}
      />
      <div className="mt-10 grid gap-4 md:grid-cols-3">
        {copy.cards.map((card) => (
          <article
            className="rounded-[14px] border border-brand-line bg-brand-paper p-6"
            key={card.title}
          >
            <h3 className="text-lg font-semibold text-brand-ink">{card.title}</h3>
            <p className="mt-3 leading-7 text-brand-slate">{card.text}</p>
          </article>
        ))}
      </div>
      <div className="mt-10">
        <p className="font-mono text-[0.74rem] uppercase tracking-[0.18em] text-brand-muted">
          {copy.chipsLabel}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {copy.chips.map((chip) => (
            <span
              className="rounded-full border border-brand-line px-3 py-1 font-mono text-xs text-brand-slate"
              key={chip}
            >
              {chip}
            </span>
          ))}
        </div>
      </div>
    </SectionShell>
  );
}
