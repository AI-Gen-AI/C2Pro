'use client';

import React, { useState, useEffect } from 'react';

interface SystemStatus {
  api_status: string;
  database_status: string;
  timestamp: string; // Add timestamp to SystemStatus
  // Add more system health metrics as needed
}

interface RecentAnalysis {
  id: string;
  project_id: string;
  status: string;
  coherence_score: number | null;
  alerts_count: number;
  started_at: string;
  completed_at: string | null;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ObservabilityPage() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [recentAnalyses, setRecentAnalyses] = useState<RecentAnalysis[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        // Fetch System Status
        const statusResponse = await fetch(`${API_BASE_URL}/api/v1/observability/status`);
        if (!statusResponse.ok) {
          throw new Error(`Error fetching system status: ${statusResponse.statusText}`);
        }
        const statusData: SystemStatus = await statusResponse.json();
        setSystemStatus(statusData);

        // Fetch Recent Analyses
        const analysesResponse = await fetch(`${API_BASE_URL}/api/v1/observability/analyses`);
        if (!analysesResponse.ok) {
          throw new Error(`Error fetching recent analyses: ${analysesResponse.statusText}`);
        }
        const analysesData: { analyses: RecentAnalysis[] } = await analysesResponse.json(); // API returns { analyses: [], total_analyses: N }
        setRecentAnalyses(analysesData.analyses);

      } catch (err: any) {
        setError(err.message);
        // Provide default error status for display
        setSystemStatus({
          api_status: 'ERROR',
          database_status: 'ERROR',
          timestamp: new Date().toISOString()
        });
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Refresh data every 30 seconds
    const interval = setInterval(fetchData, 30000); 
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto bg-white shadow-lg rounded-lg">
      <h1 className="text-3xl font-bold mb-6 text-gray-800 border-b pb-3">Observability Dashboard</h1>

      {loading && <p className="text-center text-lg text-gray-600 py-8">Loading observability data...</p>}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md relative mb-6">
          <strong className="font-bold">Error:</strong>
          <span className="block sm:inline ml-2">{error}</span>
        </div>
      )}

      {systemStatus && (
        <div className="mb-8 bg-gray-50 p-6 rounded-md shadow-inner">
          <h2 className="text-2xl font-semibold mb-4 text-gray-700">System Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-gray-700 mb-2"><strong className="font-medium">API Status:</strong>{' '}
                <span className={`font-bold ${systemStatus.api_status === 'OK' ? 'text-green-600' : 'text-red-600'}`}>
                  {systemStatus.api_status}
                </span>
              </p>
              <p className="text-gray-700 mb-2"><strong className="font-medium">Database Status:</strong>{' '}
                <span className={`font-bold ${systemStatus.database_status === 'OK' ? 'text-green-600' : 'text-red-600'}`}>
                  {systemStatus.database_status}
                </span>
              </p>
            </div>
            <div>
              <p className="text-gray-700 mb-2"><strong className="font-medium">Last Checked:</strong> {new Date(systemStatus.timestamp).toLocaleString()}</p>
            </div>
          </div>
        </div>
      )}

      {recentAnalyses.length > 0 && (
        <div className="bg-gray-50 p-6 rounded-md shadow-inner">
          <h2 className="text-2xl font-semibold mb-4 text-gray-700">Recent Coherence Analyses</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full bg-white border border-gray-200 rounded-md">
              <thead>
                <tr className="bg-gray-100 text-gray-600 uppercase text-sm leading-normal">
                  <th className="py-3 px-6 text-left border-b border-gray-200">Analysis ID</th>
                  <th className="py-3 px-6 text-left border-b border-gray-200">Project ID</th>
                  <th className="py-3 px-6 text-left border-b border-gray-200">Status</th>
                  <th className="py-3 px-6 text-left border-b border-gray-200">Score</th>
                  <th className="py-3 px-6 text-left border-b border-gray-200">Alerts</th>
                  <th className="py-3 px-6 text-left border-b border-gray-200">Started At</th>
                  <th className="py-3 px-6 text-left border-b border-gray-200">Completed At</th>
                </tr>
              </thead>
              <tbody className="text-gray-700 text-sm font-light">
                {recentAnalyses.map((analysis) => (
                  <tr key={analysis.id} className="border-b border-gray-200 hover:bg-gray-50">
                    <td className="py-3 px-6 text-left whitespace-nowrap">{analysis.id.substring(0, 8)}...</td>
                    <td className="py-3 px-6 text-left whitespace-nowrap">{analysis.project_id.substring(0, 8)}...</td>
                    <td className="py-3 px-6 text-left whitespace-nowrap">
                      <span className={`relative inline-block px-3 py-1 font-semibold text-xs leading-tight ${
                        analysis.status === 'COMPLETED' ? 'text-green-900' :
                        analysis.status === 'ERROR' ? 'text-red-900' :
                        'text-yellow-900'
                      }`}>
                        <span aria-hidden className={`absolute inset-0 opacity-50 rounded-full ${
                          analysis.status === 'COMPLETED' ? 'bg-green-200' :
                          analysis.status === 'ERROR' ? 'bg-red-200' :
                          'bg-yellow-200'
                        }`}></span>
                        <span className="relative">{analysis.status}</span>
                      </span>
                    </td>
                    <td className="py-3 px-6 text-left whitespace-nowrap">{analysis.coherence_score !== null ? analysis.coherence_score : 'N/A'}</td>
                    <td className="py-3 px-6 text-left whitespace-nowrap">{analysis.alerts_count}</td>
                    <td className="py-3 px-6 text-left whitespace-nowrap">{new Date(analysis.started_at).toLocaleString()}</td>
                    <td className="py-3 px-6 text-left whitespace-nowrap">{analysis.completed_at ? new Date(analysis.completed_at).toLocaleString() : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && !error && !systemStatus && recentAnalyses.length === 0 && (
        <p className="text-center text-lg text-gray-600 py-8">No observability data available.</p>
      )}
    </div>
  );
}