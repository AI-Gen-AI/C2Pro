/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
"use client";

import { useEffect, useRef, useState } from "react";
import {
  ScopedKeyboardShortcuts,
  type ShortcutPreferences,
} from "@/components/features/shortcuts/ScopedKeyboardShortcuts";
import { ShortcutHelpDialog } from "@/components/features/shortcuts/ShortcutHelpDialog";

const STORAGE_KEY = "s3-05-shortcut-prefs";

function readPrefs(): ShortcutPreferences {
  if (typeof window === "undefined") return {};
  const raw = window.sessionStorage.getItem(STORAGE_KEY);
  if (!raw) return {};
  try {
    return JSON.parse(raw) as ShortcutPreferences;
  } catch {
    return {};
  }
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select";
}

export function ShortcutScopeHarness() {
  const [activeScope, setActiveScope] = useState<"evidence" | "alerts">("evidence");
  const activeScopeRef = useRef<"evidence" | "alerts">("evidence");
  const [evidenceCursor, setEvidenceCursor] = useState(0);
  const [alertStatus, setAlertStatus] = useState<"pending" | "approved" | "rejected">("pending");
  const [helpOpen, setHelpOpen] = useState(false);
  const [preferences] = useState<ShortcutPreferences>(() => readPrefs());

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (isEditableTarget(event.target)) return;
      if (event.key === "?") {
        event.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <section aria-label="Shortcut Scope Harness">
      <div
        data-testid="shortcut-scope-evidence"
        tabIndex={0}
        onFocus={() => {
          activeScopeRef.current = "evidence";
          setActiveScope("evidence");
        }}
      >
        Evidence scope
      </div>
      <div data-testid="shortcut-evidence-cursor">{evidenceCursor}</div>

      <div
        data-testid="shortcut-scope-alerts"
        tabIndex={0}
        onFocus={() => {
          activeScopeRef.current = "alerts";
          setActiveScope("alerts");
        }}
      >
        Alerts scope
      </div>
      <div data-testid="shortcut-alert-status">{alertStatus}</div>

      <label htmlFor="shortcut-notes">Notes</label>
      <input id="shortcut-notes" aria-label="Notes" />

      <ScopedKeyboardShortcuts
        scopeId="evidence"
        isScopeActive
        preferences={preferences}
        bindings={{
          j: () => {
            if (activeScopeRef.current !== "evidence") return;
            setEvidenceCursor((value) => value + 1);
          },
          k: () => {
            if (activeScopeRef.current !== "evidence") return;
            setEvidenceCursor((value) => Math.max(0, value - 1));
          },
        }}
      />
      <ScopedKeyboardShortcuts
        scopeId="alerts"
        isScopeActive
        preferences={preferences}
        bindings={{
          a: () => {
            if (activeScopeRef.current !== "alerts") return;
            setAlertStatus("approved");
          },
          r: () => {
            if (activeScopeRef.current !== "alerts") return;
            setAlertStatus("rejected");
          },
        }}
      />

      <ShortcutHelpDialog
        open={helpOpen}
        activeScopes={[activeScope]}
        bindings={{
          evidence: [
            { key: "j", label: "Next highlight" },
            { key: "k", label: "Previous highlight" },
          ],
          alerts: [
            { key: "a", label: "Approve selected alert" },
            { key: "r", label: "Reject selected alert" },
          ],
        }}
      />
    </section>
  );
}
