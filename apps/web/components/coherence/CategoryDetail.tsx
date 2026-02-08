'use client';

import { Button } from '@/components/ui/button';
import { X, FileText } from 'lucide-react';
import Link from 'next/link';

const CATEGORY_META: Record<string, { label: string; color: string }> = {
  SCOPE: { label: 'Scope', color: '#00ACC1' },
  BUDGET: { label: 'Budget', color: '#6929C4' },
  QUALITY: { label: 'Quality', color: '#1192E8' },
  TECHNICAL: { label: 'Technical', color: '#005D5D' },
  LEGAL: { label: 'Legal', color: '#9F1853' },
  TIME: { label: 'Time', color: '#FA4D56' },
};

interface CategoryDetailProps {
  category: string;
  score: number;
  weight: number;
  alertCount: number;
  trend: number[];
  onClose: () => void;
}

const TREND_LABELS = ['Week 1', 'Week 2', 'Week 3', 'Current'];

export function CategoryDetail({
  category,
  score,
  weight,
  alertCount,
  trend,
  onClose,
}: CategoryDetailProps) {
  const meta = CATEGORY_META[category] ?? CATEGORY_META.SCOPE;

  return (
    <div
      className="animate-fade-in rounded-md border bg-card p-5 shadow-lg"
      style={{ borderColor: `${meta.color}40` }}
    >
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold">{meta.label} Analysis</h3>
          <span className="text-xs text-muted-foreground">
            Weight: {Math.round(weight * 100)}% &middot; {alertCount} alert
            {alertCount !== 1 ? 's' : ''}
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={onClose}>
          <X className="mr-1 h-3 w-3" />
          Close
        </Button>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {trend.map((v, i) => (
          <div
            key={i}
            className="rounded-md border p-2.5 text-center"
            style={{
              backgroundColor:
                i === trend.length - 1 ? `${meta.color}10` : 'hsl(240, 10%, 98%)',
              borderColor:
                i === trend.length - 1 ? `${meta.color}30` : 'hsl(240, 6%, 90%)',
            }}
          >
            <div className="mb-1 text-[10px] text-muted-foreground">
              {TREND_LABELS[i] || `Period ${i + 1}`}
            </div>
            <div
              className="font-mono text-lg font-semibold"
              style={{
                color: i === trend.length - 1 ? meta.color : undefined,
              }}
            >
              {v}
            </div>
          </div>
        ))}
      </div>

      {alertCount > 0 && (
        <div className="mt-3.5 flex items-center gap-2 rounded-md border border-warning/20 bg-warning-bg px-3.5 py-2.5 text-xs text-warning">
          <FileText className="h-3.5 w-3.5 shrink-0" />
          <span>
            {alertCount} document pair{alertCount !== 1 ? 's' : ''}{' '}
            require{alertCount === 1 ? 's' : ''} review in this category
            &mdash;{' '}
            <Link
              href="/evidence"
              className="font-semibold text-primary hover:underline"
            >
              View in Evidence Viewer
            </Link>
          </span>
        </div>
      )}
    </div>
  );
}
