/**
 * Test Suite ID: TASK-FRT-199
 * Backlog Task: TASK-FRT-199
 */
import Link from "next/link";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/lib/utils";

type EyebrowProps = ComponentPropsWithoutRef<"p"> & {
  onNavy?: boolean;
};

export function Eyebrow({
  children,
  className,
  onNavy = false,
  ...props
}: EyebrowProps) {
  return (
    <p
      className={cn(
        "font-mono text-[0.74rem] font-medium uppercase tracking-[0.18em]",
        onNavy ? "text-brand-accent-on-navy" : "text-brand-accent-ink",
        className,
      )}
      {...props}
    >
      {children}
    </p>
  );
}

type HeadingProps = ComponentPropsWithoutRef<"h1">;

export function Display({ children, className, ...props }: HeadingProps) {
  return (
    <h1
      className={cn(
        "font-brand-display text-5xl font-medium leading-[0.94] text-balance tracking-normal md:text-7xl",
        className,
      )}
      {...props}
    >
      {children}
    </h1>
  );
}

export function H2({ children, className, ...props }: ComponentPropsWithoutRef<"h2">) {
  return (
    <h2
      className={cn(
        "font-brand-display text-4xl font-medium leading-tight text-balance tracking-normal md:text-6xl",
        className,
      )}
      {...props}
    >
      {children}
    </h2>
  );
}

type SectionShellProps = ComponentPropsWithoutRef<"section"> & {
  variant?: "alabaster" | "paper" | "navy";
};

const sectionVariants: Record<NonNullable<SectionShellProps["variant"]>, string> = {
  alabaster: "bg-brand-alabaster text-brand-ink",
  paper: "bg-brand-paper text-brand-ink",
  navy: "bg-brand-navy text-brand-on-navy",
};

export function SectionShell({
  children,
  className,
  id,
  variant = "alabaster",
  ...props
}: SectionShellProps) {
  return (
    <section
      aria-label={id}
      className={cn(
        "px-6 py-[clamp(64px,11vw,128px)]",
        sectionVariants[variant],
        className,
      )}
      id={id}
      {...props}
    >
      <div className="mx-auto w-full max-w-[1200px]">{children}</div>
    </section>
  );
}

type SectionIntroProps = {
  eyebrow: ReactNode;
  heading: ReactNode;
  body?: ReactNode;
  onNavy?: boolean;
  className?: string;
  headingClassName?: string;
  bodyClassName?: string;
};

export function SectionIntro({
  eyebrow,
  heading,
  body,
  onNavy = false,
  className,
  headingClassName,
  bodyClassName,
}: SectionIntroProps) {
  return (
    <div className={className}>
      <Eyebrow onNavy={onNavy}>{eyebrow}</Eyebrow>
      <H2 className={cn("mt-4", headingClassName)}>{heading}</H2>
      {body ? (
        <p
          className={cn(
            "mt-5 text-lg leading-8",
            onNavy ? "text-brand-on-navy-muted" : "text-brand-slate",
            bodyClassName,
          )}
        >
          {body}
        </p>
      ) : null}
    </div>
  );
}

type BrandButtonProps = Omit<ComponentPropsWithoutRef<typeof Link>, "href"> & {
  href: string;
  children: ReactNode;
  variant?: "primary" | "ghost" | "outline";
  size?: "sm" | "lg";
  showArrow?: boolean;
};

const buttonVariants: Record<NonNullable<BrandButtonProps["variant"]>, string> = {
  primary: "bg-brand-accent text-white shadow-sm hover:bg-brand-accent-dark",
  ghost: "text-brand-accent-ink hover:bg-brand-accent-soft",
  outline:
    "border border-brand-line bg-transparent text-brand-ink hover:border-brand-accent hover:text-brand-accent-ink",
};

const buttonSizes: Record<NonNullable<BrandButtonProps["size"]>, string> = {
  sm: "h-9 px-3 text-sm",
  lg: "h-12 px-5 text-base",
};

export function BrandButton({
  children,
  className,
  variant = "primary",
  size = "lg",
  showArrow = true,
  ...props
}: BrandButtonProps) {
  return (
    <Link
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[14px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-accent focus-visible:ring-offset-2",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...props}
    >
      <span>{children}</span>
      {showArrow ? <BrandArrow /> : null}
    </Link>
  );
}

function BrandArrow() {
  return (
    <svg
      aria-hidden="true"
      className="h-4 w-4"
      data-testid="brand-button-arrow"
      fill="none"
      viewBox="0 0 16 16"
    >
      <path
        d="M3.25 8h9.5m0 0L8.75 4m4 4-4 4"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
    </svg>
  );
}

type PilotBadgeProps = ComponentPropsWithoutRef<"span">;

export function PilotBadge({ children, className, ...props }: PilotBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-brand-line bg-brand-paper px-3 py-1 text-sm font-medium text-brand-ink",
        className,
      )}
      {...props}
    >
      <span className="h-2 w-2 rounded-full bg-brand-accent" aria-hidden="true" />
      {children}
    </span>
  );
}

export function CheckList({
  children,
  className,
  ...props
}: ComponentPropsWithoutRef<"ul">) {
  return (
    <ul className={cn("space-y-3", className)} {...props}>
      {children}
    </ul>
  );
}

export function CheckItem({
  children,
  className,
  ...props
}: ComponentPropsWithoutRef<"li">) {
  return (
    <li className={cn("flex gap-3 text-brand-ink", className)} {...props}>
      <CheckIcon />
      <span>{children}</span>
    </li>
  );
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      className="mt-0.5 h-5 w-5 shrink-0 text-brand-accent"
      data-testid="check-item-icon"
      fill="none"
      viewBox="0 0 20 20"
    >
      <path
        d="m5 10.5 3 3 7-7"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}
