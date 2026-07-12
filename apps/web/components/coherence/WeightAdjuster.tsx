"use client";

import { useMemo, useState } from "react";

type WeightKey = "scope" | "budget" | "time" | "technical" | "legal" | "quality";

export type WeightMap = Record<WeightKey, number>;

export interface WeightAdjusterProps {
  onSave: (weights: WeightMap) => void;
}

const DEFAULT_WEIGHTS: WeightMap = {
  scope: 20,
  budget: 15,
  time: 20,
  technical: 15,
  legal: 15,
  quality: 15,
};

const CATEGORIES: Array<{ key: WeightKey; label: string; helper: string }> = [
  { key: "scope", label: "Scope", helper: "WBS, scope coverage" },
  { key: "budget", label: "Budget", helper: "Cost lines, deviations" },
  { key: "time", label: "Time", helper: "Milestones, schedules" },
  { key: "technical", label: "Technical", helper: "Specs, dependencies" },
  { key: "legal", label: "Legal", helper: "Compliance, approvals" },
  { key: "quality", label: "Quality", helper: "Standards, material certs" },
];

export function WeightAdjuster({ onSave }: WeightAdjusterProps) {
  const [weights, setWeights] = useState<WeightMap>(DEFAULT_WEIGHTS);

  const total = useMemo(
    () => Object.values(weights).reduce((sum, value) => sum + value, 0),
    [weights],
  );

  const isValid = total === 100;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 text-primary-text shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Weight adjuster</h2>
          <p className="text-sm text-slate-600">
            Tune how each coherence category contributes to the global score.
          </p>
        </div>
        <div
          role="status"
          aria-live="polite"
          className="rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-medium"
        >
          Total: {total}
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {CATEGORIES.map((category) => {
          const id = `weight-${category.key}`;
          return (
            <div key={category.key} className="rounded-xl border border-slate-100 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <label htmlFor={id} className="text-sm font-semibold">
                    {category.label}
                  </label>
                  <p className="text-xs text-slate-500">{category.helper}</p>
                </div>
                <span className="text-sm font-semibold tabular-nums">
                  {weights[category.key]}%
                </span>
              </div>
              <input
                id={id}
                name={category.key}
                type="range"
                min={0}
                max={100}
                step={1}
                value={weights[category.key]}
                onChange={(event) => {
                  const nextValue = Number(event.target.value);
                  setWeights((prev) => ({
                    ...prev,
                    [category.key]: nextValue,
                  }));
                }}
                className="mt-4 h-2 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-slate-900"
              />
            </div>
          );
        })}
      </div>

      <div className="mt-6 flex items-center justify-end gap-3">
        <button
          type="button"
          className="rounded-full bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:bg-slate-300"
          onClick={() => onSave(weights)}
          disabled={!isValid}
        >
          Save weights
        </button>
      </div>
    </section>
  );
}
