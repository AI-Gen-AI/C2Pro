'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface AnalysisResult {
  project_id: string;
  status: string;
  coherence_score: number | null;
  alerts_count: number;
  message: string;
  started_at?: string;
  completed_at?: string;
}

interface Alert {
  rule_id: string;
  severity: string;
  message: string;
  suggested_action: string;
  // Add more fields as per Alert model if needed
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'; // Assuming API runs on 8000

export default function ProjectAnalysisPage({ params }: { params: { id: string } }) {
  const { id: projectId } = params;
  const router = useRouter();
  const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      // Assuming an API endpoint to get the latest analysis for a project
      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/analysis`);
      if (!response.ok) {
        throw new Error(`Error fetching analysis: ${response.statusText}`);
      }
      const data = await response.json();
      setAnalysisResult(data);
      // Assuming alerts are part of the analysis result for now, or fetched separately
      // For this minimal UI, let's assume `data.alerts` or similar
      if (data.alerts && Array.isArray(data.alerts)) {
        setAlerts(data.alerts);
      } else {
        setAlerts([]); // No alerts or not in expected format
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const triggerAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      // Assuming an API endpoint to trigger analysis
      const response = await fetch(`${API_BASE_URL}/api/v1/projects/${projectId}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (!response.ok) {
        throw new Error(`Error triggering analysis: ${response.statusText}`);
      }
      const data = await response.json();
      setAnalysisResult(data);
      if (data.alerts && Array.isArray(data.alerts)) {
        setAlerts(data.alerts);
      } else {
        setAlerts([]);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
  }, [projectId]);

  return (
    <div className="p-8 max-w-4xl mx-auto bg-white shadow-lg rounded-lg">
      <h1 className="text-3xl font-bold mb-6 text-gray-800">Project Analysis for ID: {projectId}</h1>

      <button
        onClick={triggerAnalysis}
        disabled={loading}
        className={`px-6 py-3 text-lg font-semibold text-white rounded-md transition-colors duration-200 ${
          loading ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
        } focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50 mb-8`}
      >
        {loading ? 'Analyzing...' : 'Trigger New Analysis'}
      </button>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-md relative mb-6">
          <strong className="font-bold">Error:</strong>
          <span className="block sm:inline ml-2">{error}</span>
        </div>
      )}

      {analysisResult ? (
        <div className="bg-gray-50 p-6 rounded-md shadow-inner mb-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-700 border-b pb-2">Analysis Summary</h2>
          <p className="text-gray-700 mb-2"><strong className="font-medium">Status:</strong> {analysisResult.status}</p>
          <p className="text-gray-700 mb-2">
            <strong className="font-medium">Coherence Score:</strong>{' '}
            {analysisResult.coherence_score !== null ? (
              <span className={`font-bold ${
                (analysisResult.coherence_score || 0) >= 80 ? 'text-green-600' :
                (analysisResult.coherence_score || 0) >= 50 ? 'text-yellow-600' :
                'text-red-600'
              }`}>
                {analysisResult.coherence_score}
              </span>
            ) : (
              'N/A'
            )}
          </p>
          <p className="text-gray-700 mb-2"><strong className="font-medium">Number of Alerts:</strong> {analysisResult.alerts_count}</p>
          <p className="text-gray-700 mb-2"><strong className="font-medium">Message:</strong> {analysisResult.message}</p>
          {analysisResult.started_at && <p className="text-gray-700 mb-2"><strong className="font-medium">Started At:</strong> {new Date(analysisResult.started_at).toLocaleString()}</p>}
          {analysisResult.completed_at && <p className="text-gray-700 mb-2"><strong className="font-medium">Completed At:</strong> {new Date(analysisResult.completed_at).toLocaleString()}</p>}
        </div>
      ) : (
        <p className="text-gray-600 text-lg text-center py-8">No analysis data available. Trigger an analysis to view results.</p>
      )}

      {alerts.length > 0 && (
        <div className="mt-8">
          <h2 className="text-2xl font-semibold mb-4 text-gray-700 border-b pb-2">Detected Inconsistencies ({alerts.length})</h2>
          {alerts.map((alert, index) => (
            <div
              key={index}
              className="bg-white border border-gray-200 rounded-md p-6 mb-4 shadow-sm"
            >
              <h3 className={`text-xl font-bold mb-2 ${
                alert.severity === 'critical' ? 'text-red-600' :
                alert.severity === 'high' ? 'text-orange-600' :
                alert.severity === 'medium' ? 'text-yellow-600' :
                'text-gray-700'
              }`}>
                Rule: {alert.rule_id} - {alert.severity.toUpperCase()}
              </h3>
              <p className="text-gray-700 mb-2"><strong className="font-medium">Message:</strong> {alert.message}</p>
              <p className="text-gray-700"><strong className="font-medium">Suggested Action:</strong> {alert.suggested_action}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}