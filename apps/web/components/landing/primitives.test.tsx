/**
 * Test Suite ID: TASK-FRT-199
 * Backlog Task: TASK-FRT-199
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import {
  BrandButton,
  CheckItem,
  CheckList,
  Display,
  Eyebrow,
  H2,
  PilotBadge,
  SectionShell,
} from "./primitives";

describe("landing primitives", () => {
  it("renders the eyebrow with mono uppercase brand styling", () => {
    render(<Eyebrow>Programa piloto</Eyebrow>);

    const eyebrow = screen.getByText("Programa piloto");
    expect(eyebrow).toHaveClass(
      "font-mono",
      "uppercase",
      "tracking-[0.18em]",
      "text-brand-accent-ink",
    );
  });

  it("switches the eyebrow color for navy surfaces", () => {
    render(<Eyebrow onNavy>Programa piloto</Eyebrow>);

    expect(screen.getByText("Programa piloto")).toHaveClass(
      "text-brand-accent-on-navy",
    );
  });

  it("renders display headings with the brand display font", () => {
    render(
      <>
        <Display>Hero title</Display>
        <H2>Section title</H2>
      </>,
    );

    expect(screen.getByRole("heading", { name: "Hero title" })).toHaveClass(
      "font-brand-display",
      "font-medium",
      "leading-[0.94]",
    );
    expect(screen.getByRole("heading", { name: "Section title" })).toHaveClass(
      "font-brand-display",
      "font-medium",
      "leading-tight",
    );
  });

  it("wraps section content in the requested brand surface", () => {
    render(
      <SectionShell id="waitlist" variant="navy">
        <p>Waitlist content</p>
      </SectionShell>,
    );

    const section = screen.getByRole("region", { name: "waitlist" });
    expect(section).toHaveAttribute("id", "waitlist");
    expect(section).toHaveClass("bg-brand-navy", "text-brand-on-navy");
    expect(section.firstElementChild).toHaveClass("max-w-[1200px]");
  });

  it("renders brand button variants with the teal primary and arrow slot", () => {
    render(
      <>
        <BrandButton href="#waitlist">Primary action</BrandButton>
        <BrandButton href="/demo" variant="outline" showArrow={false}>
          Outline action
        </BrandButton>
        <BrandButton href="/login" variant="ghost" size="sm">
          Ghost action
        </BrandButton>
      </>,
    );

    expect(screen.getByRole("link", { name: /Primary action/ })).toHaveClass(
      "bg-brand-accent",
      "hover:bg-brand-accent-dark",
      "text-white",
    );
    expect(screen.getAllByTestId("brand-button-arrow")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "Outline action" })).toHaveClass(
      "border-brand-line",
      "text-brand-ink",
    );
    expect(screen.getByRole("link", { name: "Ghost action" })).toHaveClass(
      "text-brand-accent-ink",
      "h-9",
    );
  });

  it("renders the pilot badge and checklist items", () => {
    render(
      <>
        <PilotBadge>Programa piloto · en validación</PilotBadge>
        <CheckList>
          <CheckItem>Evidence-first review</CheckItem>
        </CheckList>
      </>,
    );

    expect(screen.getByText("Programa piloto · en validación")).toHaveClass(
      "rounded-full",
      "border-brand-line",
    );
    expect(screen.getByRole("list")).toBeInTheDocument();
    expect(screen.getByRole("listitem")).toHaveTextContent(
      "Evidence-first review",
    );
    expect(screen.getByTestId("check-item-icon")).toHaveClass(
      "text-brand-accent",
    );
  });
});
