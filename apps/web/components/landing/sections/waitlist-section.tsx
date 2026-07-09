/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy, LandingLocale } from "../copy";
import { CheckItem, CheckList, Eyebrow, H2, SectionShell } from "../primitives";
import { WaitlistForm } from "./waitlist-form";

type WaitlistSectionProps = {
  copy: LandingCopy["waitlist"];
  locale: LandingLocale;
};

export function WaitlistSection({ copy, locale }: WaitlistSectionProps) {
  return (
    <SectionShell id="waitlist" variant="navy">
      <div className="grid gap-10 lg:grid-cols-[1fr_0.8fr] lg:items-start">
        <div>
          <Eyebrow onNavy>{copy.eyebrow}</Eyebrow>
          <H2 className="mt-4 text-brand-on-navy">{copy.h2}</H2>
          <p className="mt-5 text-lg leading-8 text-brand-on-navy-muted">
            {copy.lead}
          </p>
          <CheckList className="mt-8">
            {copy.checks.map((check) => (
              <CheckItem className="text-brand-on-navy" key={check}>
                {check}
              </CheckItem>
            ))}
          </CheckList>
        </div>
        <WaitlistForm copy={copy} locale={locale} />
      </div>
    </SectionShell>
  );
}
