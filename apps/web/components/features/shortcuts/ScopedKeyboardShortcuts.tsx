/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
"use client";

import { useEffect } from "react";

type ShortcutHandler = () => void;

export interface ShortcutPreferences {
  disabled?: boolean;
  remap?: Record<string, string>;
}

interface ScopedKeyboardShortcutsProps {
  scopeId: string;
  isScopeActive: boolean;
  bindings: Record<string, ShortcutHandler>;
  preferences?: ShortcutPreferences;
}

function normalizeKey(key: string): string {
  return key.toLowerCase();
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select";
}

function isReservedCombo(event: KeyboardEvent): boolean {
  return event.ctrlKey || event.metaKey || event.altKey;
}

export function ScopedKeyboardShortcuts({
  scopeId,
  isScopeActive,
  bindings,
  preferences,
}: ScopedKeyboardShortcutsProps) {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!isScopeActive) return;
      if (preferences?.disabled) return;
      if (isReservedCombo(event)) return;
      if (isEditableTarget(event.target)) return;

      const key = normalizeKey(event.key);
      const originalKey = Object.entries(preferences?.remap ?? {}).find(
        ([from, to]) => normalizeKey(to) === key && normalizeKey(from) in bindings,
      )?.[0];

      const bindingKey = normalizeKey(originalKey ?? key);
      const action = Object.entries(bindings).find(
        ([candidate]) => normalizeKey(candidate) === bindingKey,
      )?.[1];

      if (!action) return;
      event.preventDefault();
      action();
    };

    window.addEventListener("keydown", handler);
    return () => {
      window.removeEventListener("keydown", handler);
    };
  }, [bindings, isScopeActive, preferences]);

  return <span data-testid={`shortcut-scope-handler-${scopeId}`} hidden />;
}

