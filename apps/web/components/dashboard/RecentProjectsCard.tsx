import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import type { Project, ProjectStatus } from '@/types/project';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';

interface RecentProjectsCardProps {
  projects: Project[];
  className?: string;
}

const statusConfig: Record<
  ProjectStatus,
  { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive' }
> = {
  draft: { label: 'Draft', variant: 'outline' },
  active: { label: 'Active', variant: 'default' },
  on_hold: { label: 'On Hold', variant: 'outline' },
  completed: { label: 'Completed', variant: 'secondary' },
  archived: { label: 'Archived', variant: 'outline' },
};

const getScoreColor = (score: number) => {
  if (score >= 80) return 'score-good';
  if (score >= 60) return 'score-fair';
  return 'score-poor';
};

export function RecentProjectsCard({ projects, className }: RecentProjectsCardProps) {
  const recentProjects = projects.slice(0, 5);

  return (
    <Card className={cn('card-interactive', className)}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-semibold">Recent Projects</CardTitle>
        <Link href="/projects">
          <Button variant="ghost" size="sm" className="gap-1 text-xs">
            View All
            <ArrowRight className="h-3 w-3" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {recentProjects.map((project) => {
            const status = statusConfig[project.status];

            return (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="flex items-center gap-4 rounded-lg border p-3 transition-colors hover:bg-muted/50"
              >
                {/* Project Info */}
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">
                      {project.id}
                    </span>
                    <Badge variant={status.variant} className="text-xs">
                      {status.label}
                    </Badge>
                    {/* Alerts */}
                    {project.critical_alerts && project.critical_alerts > 0 && (
                      <Badge variant="destructive" className="animate-pulse-critical">
                        {project.critical_alerts} Critical
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm font-medium">{project.name}</p>
                </div>

                {/* Score */}
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className={cn('text-lg font-bold', project.coherence_score !== undefined ? getScoreColor(project.coherence_score) : 'text-muted-foreground')}>
                      {project.coherence_score ?? '--'}
                    </div>
                    <div className="text-xs text-muted-foreground">Score</div>
                  </div>
                  <Progress
                    value={project.coherence_score ?? 0}
                    className="h-2 w-16"
                  />
                </div>
              </Link>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
