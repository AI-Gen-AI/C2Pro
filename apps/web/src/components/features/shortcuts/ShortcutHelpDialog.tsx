/**
 * Test Suite ID: S3-05
 * Roadmap Reference: S3-05 Focus-scoped keyboard shortcuts (WCAG 2.1.4)
 */
"use client";

interface ScopeBinding {
  key: string;
  label: string;
}

interface ShortcutHelpDialogProps {
  open: boolean;
  activeScopes: string[];
  bindings: Record<string, ScopeBinding[]>;
}

export function ShortcutHelpDialog({
  open,
  activeScopes,
  bindings,
}: ShortcutHelpDialogProps) {
  if (!open) return null;

  const visibleBindings = activeScopes.flatMap((scope) => bindings[scope] ?? []);

  return (
    <div role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
      <h2>Keyboard shortcuts</h2>
      <ul>
        {visibleBindings.map((binding) => (
          <li key={`${binding.key}-${binding.label}`}>
            <kbd>{binding.key}</kbd> <span>{binding.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

