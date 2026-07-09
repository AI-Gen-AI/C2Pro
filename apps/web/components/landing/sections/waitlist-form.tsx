"use client";

/**
 * Test Suite ID: TASK-FRT-201
 * Backlog Task: TASK-FRT-201
 */
import { useState, type FormEvent, type ReactNode } from "react";
import type { LandingCopy, LandingLocale } from "../copy";
import { waitlistSchema, type WaitlistFormData } from "../waitlist-schema";

type WaitlistFormProps = {
  copy: LandingCopy["waitlist"];
  locale: LandingLocale;
};

type FormState = {
  name: string;
  company: string;
  role: string;
  email: string;
  volume: "" | NonNullable<WaitlistFormData["volume"]>;
  consent: boolean;
  website: string;
};

type FieldErrors = Partial<Record<keyof FormState, string>>;

const initialFormState: FormState = {
  name: "",
  company: "",
  role: "",
  email: "",
  volume: "",
  consent: false,
  website: "",
};

const requiredError = {
  es: "Campo obligatorio.",
  en: "Required field.",
} as const;

function fieldErrorFor(locale: LandingLocale) {
  return requiredError[locale];
}

export function WaitlistForm({ copy, locale }: WaitlistFormProps) {
  const [form, setForm] = useState<FormState>(initialFormState);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  function updateField<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: undefined }));
    setSubmitError(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const parsed = waitlistSchema.safeParse({
      ...form,
      volume: form.volume || undefined,
      locale,
    });

    if (!parsed.success) {
      const flattened = parsed.error.flatten().fieldErrors;
      setErrors({
        name: flattened.name?.[0] ? fieldErrorFor(locale) : undefined,
        company: flattened.company?.[0] ? fieldErrorFor(locale) : undefined,
        email: flattened.email?.[0] ? fieldErrorFor(locale) : undefined,
        consent: flattened.consent?.[0] ? fieldErrorFor(locale) : undefined,
        website: flattened.website?.[0] ? fieldErrorFor(locale) : undefined,
      });
      return;
    }

    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed.data),
      });

      if (!response.ok) {
        throw new Error("waitlist submit failed");
      }

      const result = (await response.json()) as { success?: boolean };

      if (!result.success) {
        throw new Error("waitlist submit failed");
      }

      setIsSubmitted(true);
    } catch {
      setSubmitError(copy.form.error);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isSubmitted) {
    return (
      <div className="rounded-[14px] border border-brand-accent-on-navy/40 bg-brand-navy-panel p-6">
        <h3 className="font-brand-display text-3xl font-medium text-brand-on-navy">
          {copy.formTitle}
        </h3>
        <p className="mt-5 leading-7 text-brand-on-navy-muted">
          {copy.form.success}
        </p>
      </div>
    );
  }

  return (
    <form
      className="rounded-[14px] border border-brand-accent-on-navy/40 bg-brand-navy-panel p-6"
      noValidate
      onSubmit={onSubmit}
    >
      <h3 className="font-brand-display text-3xl font-medium text-brand-on-navy">
        {copy.formTitle}
      </h3>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Field
          error={errors.name}
          id="waitlist-name"
          label={copy.form.fields.name.label}
        >
          <input
            className="h-11 w-full rounded-[10px] border border-brand-on-navy-muted/30 bg-brand-navy px-3 text-brand-on-navy placeholder:text-brand-on-navy-muted"
            id="waitlist-name"
            onChange={(event) => updateField("name", event.target.value)}
            placeholder={copy.form.fields.name.placeholder}
            value={form.name}
          />
        </Field>
        <Field
          error={errors.company}
          id="waitlist-company"
          label={copy.form.fields.company.label}
        >
          <input
            className="h-11 w-full rounded-[10px] border border-brand-on-navy-muted/30 bg-brand-navy px-3 text-brand-on-navy placeholder:text-brand-on-navy-muted"
            id="waitlist-company"
            onChange={(event) => updateField("company", event.target.value)}
            placeholder={copy.form.fields.company.placeholder}
            value={form.company}
          />
        </Field>
        <Field id="waitlist-role" label={copy.form.fields.role.label}>
          <input
            className="h-11 w-full rounded-[10px] border border-brand-on-navy-muted/30 bg-brand-navy px-3 text-brand-on-navy placeholder:text-brand-on-navy-muted"
            id="waitlist-role"
            onChange={(event) => updateField("role", event.target.value)}
            placeholder={copy.form.fields.role.placeholder}
            value={form.role}
          />
        </Field>
        <Field
          error={errors.email}
          id="waitlist-email"
          label={copy.form.fields.email.label}
        >
          <input
            className="h-11 w-full rounded-[10px] border border-brand-on-navy-muted/30 bg-brand-navy px-3 text-brand-on-navy placeholder:text-brand-on-navy-muted"
            id="waitlist-email"
            onChange={(event) => updateField("email", event.target.value)}
            placeholder={copy.form.fields.email.placeholder}
            type="email"
            value={form.email}
          />
        </Field>
        <Field
          className="sm:col-span-2"
          id="waitlist-volume"
          label={copy.form.fields.volume.label}
        >
          <select
            className="h-11 w-full rounded-[10px] border border-brand-on-navy-muted/30 bg-brand-navy px-3 text-brand-on-navy"
            id="waitlist-volume"
            onChange={(event) =>
              updateField("volume", event.target.value as FormState["volume"])
            }
            value={form.volume}
          >
            <option value="" />
            {copy.form.fields.volume.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <div className="relative">
        <label className="sr-only" htmlFor="waitlist-website">
          Website
        </label>
        <input
          aria-hidden="true"
          autoComplete="off"
          className="absolute -left-[9999px] h-px w-px opacity-0"
          id="waitlist-website"
          onChange={(event) => updateField("website", event.target.value)}
          tabIndex={-1}
          value={form.website}
        />
      </div>
      <div className="mt-5">
        <label className="flex gap-3 text-sm leading-6 text-brand-on-navy-muted">
          <input
            checked={form.consent}
            className="mt-1 h-4 w-4 shrink-0 rounded border-brand-on-navy-muted/40"
            onChange={(event) => updateField("consent", event.target.checked)}
            type="checkbox"
          />
          <span>
            {copy.form.consent.beforeLink}{" "}
            <a
              className="text-brand-accent-on-navy underline underline-offset-4"
              href="https://www.ai-gen.ai/privacidad"
              rel="noopener"
            >
              {copy.form.consent.linkLabel}
            </a>
            {copy.form.consent.afterLink}
          </span>
        </label>
        {errors.consent ? <ErrorText>{errors.consent}</ErrorText> : null}
      </div>
      {submitError ? (
        <p className="mt-4 rounded-[10px] border border-brand-risk-soft bg-brand-risk-soft px-3 py-2 text-sm text-brand-risk-ink">
          {submitError}
        </p>
      ) : null}
      <button
        className="mt-6 inline-flex h-11 items-center justify-center rounded-[12px] bg-brand-accent px-5 text-sm font-medium text-white hover:bg-brand-accent-dark disabled:cursor-not-allowed disabled:opacity-70"
        disabled={isSubmitting}
        type="submit"
      >
        {isSubmitting ? "..." : copy.form.submit}
      </button>
    </form>
  );
}

function Field({
  children,
  className = "",
  error,
  id,
  label,
}: {
  children: ReactNode;
  className?: string;
  error?: string;
  id: string;
  label: string;
}) {
  return (
    <div className={className}>
      <label className="block text-sm font-medium text-brand-on-navy" htmlFor={id}>
        {label}
      </label>
      <div className="mt-2">{children}</div>
      {error ? <ErrorText>{error}</ErrorText> : null}
    </div>
  );
}

function ErrorText({ children }: { children: ReactNode }) {
  return <p className="mt-2 text-sm text-brand-accent-on-navy">{children}</p>;
}
