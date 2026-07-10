/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy, LandingLocale } from "../copy";
import { CheckItem, CheckList, SectionIntro, SectionShell } from "../primitives";
import { WaitlistForm } from "./waitlist-form";

type WaitlistSectionProps = Readonly<{
  copy: LandingCopy["waitlist"];
  locale: LandingLocale;
}>;

export function WaitlistSection({ copy, locale }: WaitlistSectionProps) {
  return (
    <SectionShell id="waitlist" variant="navy">
      <div className="grid gap-10 lg:grid-cols-[1fr_0.8fr] lg:items-start">
        <div>
          <SectionIntro
            eyebrow={copy.eyebrow}
            heading={copy.h2}
            body={copy.lead}
            onNavy
            headingClassName="text-brand-on-navy"
          />
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
