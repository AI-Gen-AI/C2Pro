"use client";

import { useState } from 'react';
import { GaugeChart } from '@/components/dashboard/GaugeChart';
import { KPICardsGrid } from '@/components/dashboard/KPICards';
import { ActivityTimeline } from '@/components/dashboard/ActivityTimeline';
import { TopAlertsCard } from '@/components/dashboard/TopAlertsCard';
import { RecentProjectsCard } from '@/components/dashboard/RecentProjectsCard';
import { CoherenceScoreModal } from '@/components/coherence/CoherenceScoreModal';
import { mockKPIData, mockActivities, mockAlerts, mockProjects } from '@/lib/mockData';
import { MOCK_COHERENCE_DETAIL } from '@/types/coherence';

export default function DashboardPage() {
  const [scoreModalOpen, setScoreModalOpen] = useState(false);

  return (
    <section className="space-y-6">
      {/* Top Row: Gauge + KPIs */}
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <GaugeChart
          value={mockKPIData.coherenceScore}
          trend={mockKPIData.coherenceTrend}
          onClick={() => setScoreModalOpen(true)}
        />
        <KPICardsGrid />
      </div>

      {/* Middle Row: Activity Timeline */}
      <ActivityTimeline activities={mockActivities} />

      {/* Bottom Row: Top Alerts + Recent Projects */}
      <div className="grid gap-6 lg:grid-cols-2">
        <TopAlertsCard alerts={mockAlerts} />
        <RecentProjectsCard projects={mockProjects} />
      </div>

      {/* Coherence Score Modal */}
      <CoherenceScoreModal
        isOpen={scoreModalOpen}
        onClose={() => setScoreModalOpen(false)}
        scoreDetail={MOCK_COHERENCE_DETAIL}
      />
    </section>
  );
}
