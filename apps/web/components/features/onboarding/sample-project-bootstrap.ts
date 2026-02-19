/**
 * Test Suite ID: S3-11
 * Roadmap Reference: S3-11 Onboarding sample project frontend
 */

export type BootstrapState = "idle" | "provisioning" | "ready" | "failed";
export type BootstrapEvent = "start" | "success" | "error" | "retry";

export function transitionBootstrapState(
  current: BootstrapState,
  event: BootstrapEvent,
): BootstrapState {
  if (current === "idle" && event === "start") return "provisioning";
  if (current === "provisioning" && event === "success") return "ready";
  if (current === "provisioning" && event === "error") return "failed";
  if (current === "failed" && event === "retry") return "provisioning";
  return current;
}

