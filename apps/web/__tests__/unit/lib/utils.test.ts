import { describe, expect, it } from "vitest";

import { cn } from "@/lib/utils";

describe("cn", () => {
  it("merges class names and tailwind conflicts", () => {
    const result = cn("px-2", "px-4", "text-sm", ["text-sm", "text-lg"]);
    expect(result).toBe("px-4 text-lg");
  });
});
