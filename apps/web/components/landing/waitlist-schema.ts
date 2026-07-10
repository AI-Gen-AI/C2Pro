/**
 * Test Suite ID: TASK-FRT-201
 * Backlog Task: TASK-FRT-201
 */
import { z } from "zod";

const optionalTrimmedText = z.preprocess(
  (value) => {
    if (typeof value !== "string") {
      return value;
    }

    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  },
  z.string().max(120).optional(),
);

export const waitlistVolumeOptions = ["under_20", "20_100", "over_100"] as const;

export const waitlistSchema = z.object({
  name: z.string().trim().min(1).max(120),
  company: z.string().trim().min(1).max(120),
  role: optionalTrimmedText,
  email: z.string().trim().toLowerCase().email().max(254),
  volume: z.enum(waitlistVolumeOptions).optional(),
  consent: z.literal(true),
  locale: z.enum(["es", "en"]).optional(),
  website: z.literal(""),
});

export type WaitlistFormData = z.infer<typeof waitlistSchema>;
