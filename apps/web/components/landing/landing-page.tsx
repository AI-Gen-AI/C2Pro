/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200, TASK-FRT-202
 */
import { landingCopy, type LandingLocale } from "./copy";
import { landingFontClasses } from "./fonts";
import { LandingJsonLd } from "./json-ld";
import { Reveal } from "./reveal";
import { Dimensions } from "./sections/dimensions";
import { Hero } from "./sections/hero";
import { HowItWorks } from "./sections/how-it-works";
import { LandingFooter } from "./sections/landing-footer";
import { LandingHeader } from "./sections/landing-header";
import { OriginLimits } from "./sections/origin-limits";
import { Supervision } from "./sections/supervision";
import { WaitlistSection } from "./sections/waitlist-section";

type LandingPageProps = Readonly<{
  locale: LandingLocale;
}>;

export function LandingPage({ locale }: LandingPageProps) {
  const copy = landingCopy[locale];

  return (
    <div className={`${landingFontClasses} bg-brand-alabaster text-brand-ink`}>
      <LandingJsonLd locale={locale} />
      <LandingHeader copy={copy.header} locale={locale} />
      <main>
        <Hero copy={copy.hero} consoleCopy={copy.console} />
        <Reveal>
          <Dimensions copy={copy.dimensions} />
        </Reveal>
        <Reveal>
          <Supervision copy={copy.supervision} />
        </Reveal>
        <Reveal>
          <HowItWorks copy={copy.howItWorks} />
        </Reveal>
        <Reveal>
          <OriginLimits copy={copy.originLimits} />
        </Reveal>
        <Reveal>
          <WaitlistSection copy={copy.waitlist} locale={locale} />
        </Reveal>
      </main>
      <LandingFooter copy={copy.footer} />
    </div>
  );
}
