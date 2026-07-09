/**
 * Test Suite ID: TASK-FRT-198
 * Backlog Task: TASK-FRT-198
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export type LandingAuthLabels = {
  signIn?: string;
  joinPilot?: string;
  workspace?: string;
};

type LandingAuthButtonsProps = {
  labels?: LandingAuthLabels;
};

const defaultLabels = {
  signIn: "Iniciar sesión",
  joinPilot: "Unirse al piloto",
  workspace: "Ir al workspace",
} satisfies Required<LandingAuthLabels>;

export function LandingAuthButtons({ labels = {} }: LandingAuthButtonsProps) {
  const { isLoaded, isSignedIn } = useAuth();
  const showWorkspace = isLoaded && isSignedIn;
  const copy = { ...defaultLabels, ...labels };

  return (
    <div className="flex items-center gap-3">
      {showWorkspace ? (
        <Button asChild size="sm" className="bg-primary hover:bg-primary/90">
          <Link href="/dashboard">{copy.workspace}</Link>
        </Button>
      ) : (
        <>
          <Button asChild variant="ghost" size="sm">
            <Link href="/login">{copy.signIn}</Link>
          </Button>
          <Button asChild size="sm" className="bg-primary hover:bg-primary/90">
            <a href="#waitlist">{copy.joinPilot}</a>
          </Button>
        </>
      )}
    </div>
  );
}
