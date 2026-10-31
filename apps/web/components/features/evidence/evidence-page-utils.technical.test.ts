import { describe, expect, it } from "vitest";
import { technicalSourcePresentation } from "./evidence-page-utils";

describe("technical source evidence presentation", () => {
  it("shows a real section with unverified status, not a WBS association", () => {
    expect(
      technicalSourcePresentation({
        technical_requirement: {
          source_section: "4.1.2",
          verification_status: "unverified",
        },
      }),
    ).toEqual({
      technicalSourceSection: "4.1.2",
      technicalSourceUnverified: true,
    });
  });

  it("does not invent section from arbitrary metadata or invalid locator", () => {
    expect(technicalSourcePresentation({})).toEqual({
      technicalSourceSection: null,
      technicalSourceUnverified: false,
    });
    expect(
      technicalSourcePresentation({
        technical_requirement: { source_section: "5.1 click here", verification_status: "unverified" },
      }),
    ).toEqual({ technicalSourceSection: null, technicalSourceUnverified: false });
  });

  it("does not mark a source as unverified when that status is absent", () => {
    expect(
      technicalSourcePresentation({
        technical_requirement: { source_section: "3.2" },
      }),
    ).toEqual({ technicalSourceSection: "3.2", technicalSourceUnverified: false });
  });
});
