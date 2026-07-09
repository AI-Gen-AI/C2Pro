/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy } from "../copy";
import { CheckItem, CheckList, SectionIntro, SectionShell } from "../primitives";

type SupervisionProps = {
  copy: LandingCopy["supervision"];
};

export function Supervision({ copy }: SupervisionProps) {
  return (
    <SectionShell id="supervision" variant="alabaster">
      <div className="grid gap-10 lg:grid-cols-[0.9fr_1fr] lg:items-start">
        <SectionIntro eyebrow={copy.eyebrow} heading={copy.h2} body={copy.prose} />
        <CheckList className="rounded-[14px] border border-brand-line bg-brand-paper p-6">
          {copy.bullets.map((bullet) => (
            <CheckItem key={bullet.strong}>
              <strong>{bullet.strong}</strong>
              {bullet.text}
            </CheckItem>
          ))}
        </CheckList>
      </div>
    </SectionShell>
  );
}
