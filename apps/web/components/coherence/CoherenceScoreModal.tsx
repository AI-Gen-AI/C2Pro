import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { CategoryBreakdownCard } from './CategoryBreakdownCard';
import type { CoherenceScoreDetail } from '@/types/coherence';
import { Download, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CoherenceScoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  scoreDetail: CoherenceScoreDetail | null;
}

export function CoherenceScoreModal({
  isOpen,
  onClose,
  scoreDetail,
}: CoherenceScoreModalProps) {
  if (!scoreDetail) {
    return null;
  }

  const { overall_score, category_breakdown, calculated_at } = scoreDetail;

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  const getScoreLabel = (score: number) => {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Fair';
    return 'Poor';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-2xl">Coherence Score Breakdown</DialogTitle>
          <DialogDescription>
            Detailed analysis of project coherence by category
          </DialogDescription>
        </DialogHeader>

        {/* Overall Score Section */}
        <div className="space-y-4 py-4">
          <div className="rounded-lg border bg-card p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-medium text-muted-foreground">
                  Overall Score
                </h3>
                <div className="flex items-baseline gap-2 mt-1">
                  <span className={cn('text-5xl font-bold', getScoreColor(overall_score))}>
                    {overall_score}
                  </span>
                  <span className="text-xl text-muted-foreground">/ 100</span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  Status: <span className={cn('font-semibold', getScoreColor(overall_score))}>
                    {getScoreLabel(overall_score)}
                  </span>
                </p>
              </div>
              <div className="text-right text-sm text-muted-foreground">
                <p>Calculated at:</p>
                <p className="font-medium">
                  {new Date(calculated_at).toLocaleString()}
                </p>
              </div>
            </div>
            <Progress value={overall_score} className="h-3" />
          </div>

          {/* Category Breakdown Grid */}
          <div>
            <h3 className="text-lg font-semibold mb-4">Category Breakdown</h3>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {category_breakdown.map((breakdown) => (
                <CategoryBreakdownCard
                  key={breakdown.category}
                  breakdown={breakdown}
                />
              ))}
            </div>
          </div>

          {/* Summary Stats */}
          <div className="rounded-lg border bg-muted/50 p-4">
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold">
                  {category_breakdown.reduce((sum, b) => sum + b.alert_count, 0)}
                </p>
                <p className="text-sm text-muted-foreground">Total Alerts</p>
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {category_breakdown.length}
                </p>
                <p className="text-sm text-muted-foreground">Categories</p>
              </div>
              <div>
                <p className="text-2xl font-bold">
                  {category_breakdown.reduce(
                    (sum, b) => sum + b.severity_breakdown.critical,
                    0
                  )}
                </p>
                <p className="text-sm text-muted-foreground">Critical Issues</p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 justify-end pt-4 border-t">
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Export Report
            </Button>
            <Button>
              <ExternalLink className="mr-2 h-4 w-4" />
              View All Alerts
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
