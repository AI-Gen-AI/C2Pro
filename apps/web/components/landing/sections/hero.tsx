/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy } from "../copy";
import { BrandButton, Display, PilotBadge } from "../primitives";
import { ConsoleMock } from "./console-mock";

type HeroProps = {
  copy: LandingCopy["hero"];
  consoleCopy: LandingCopy["console"];
};

export function Hero({ copy, consoleCopy }: HeroProps) {
  return (
    <section className="px-6 py-[clamp(64px,11vw,128px)]">
      <div className="mx-auto grid max-w-[1200px] gap-12 lg:grid-cols-[1fr_0.9fr] lg:items-center">
        <div>
          <PilotBadge>{copy.badge}</PilotBadge>
          <Display className="mt-8 max-w-3xl">{copy.h1}</Display>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-brand-slate">
            {copy.lead}
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <BrandButton href="#waitlist">{copy.ctaPrimary}</BrandButton>
            <BrandButton href="/demo/coherence-v1" showArrow={false} variant="outline">
              {copy.ctaSecondary}
            </BrandButton>
          </div>
          <p className="mt-6 flex gap-2 text-sm text-brand-muted">
            <span className="text-brand-accent" aria-hidden="true">
              ✓
            </span>
            {copy.trustNote}
          </p>
        </div>
        <ConsoleMock copy={consoleCopy} />
      </div>
    </section>
  );
}
