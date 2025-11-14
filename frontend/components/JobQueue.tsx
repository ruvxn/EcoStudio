'use client';

import { useEffect, useState } from 'react';
import { jobsAPI, Job } from '@/lib/api';
import { format, parseISO, formatDistanceToNow } from 'date-fns';

interface JobQueueProps {
  limit?: number;
  autoRefresh?: boolean;
}

export default function JobQueue({ limit = 20, autoRefresh = true }: JobQueueProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'queued' | 'running' | 'completed' | 'failed'>('all');

  const fetchJobs = async () => {
    try {
      const params: any = { limit };
      if (filter !== 'all') {
        params.status = filter;
      }

      const data = await jobsAPI.getJobs(params);
      setJobs(data.jobs);
      setError(null);
    } catch (err) {
      console.error('Error fetching jobs:', err);
      setError('Failed to load jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();

    if (autoRefresh) {
      // Refresh every 30 seconds
      const interval = setInterval(fetchJobs, 30 * 1000);
      return () => clearInterval(interval);
    }
  }, [filter, limit, autoRefresh]);

  const getStatusColor = (status: Job['status']) => {
    switch (status) {
      case 'queued':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'running':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'completed':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'failed':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'cancelled':
        return 'bg-gray-100 text-gray-800 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusIcon = (status: Job['status']) => {
    const iconClasses = "w-5 h-5";
    switch (status) {
      case 'queued':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'running':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        );
      case 'completed':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'failed':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'cancelled':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
          </svg>
        );
      default:
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
    }
  };

  const getJobTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      RETRAIN_MODEL: 'Model Retraining',
      GENERATE_CONTENT: 'Content Generation',
      SYNC_POSTS: 'Sync Posts',
      POST_CONTENT: 'Post Content',
      FETCH_CARBON_FORECAST: 'Fetch Carbon Forecast',
      CALCULATE_ENGAGEMENT: 'Calculate Engagement',
    };
    return labels[type] || type;
  };

  const getCarbonBadge = (intensity: number | null) => {
    if (!intensity) return null;

    let color = 'bg-gray-100 text-gray-700';
    let label = 'Unknown';

    if (intensity < 300) {
      color = 'bg-green-100 text-green-700';
      label = 'Low';
    } else if (intensity < 500) {
      color = 'bg-yellow-100 text-yellow-700';
      label = 'Medium';
    } else {
      color = 'bg-red-100 text-red-700';
      label = 'High';
    }

    return (
      <span className={`px-2 py-1 text-xs rounded-full ${color}`}>
        {label} ({intensity} g)
      </span>
    );
  };

  if (loading) {
    return (
      <div className="w-full bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-200 rounded mb-2"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full bg-white rounded-lg border border-red-200 p-6">
        <div className="text-center text-red-600">
          <svg className="w-12 h-12 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="font-medium">{error}</p>
          <button
            onClick={fetchJobs}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Job Queue</h2>
          <p className="text-sm text-gray-600 mt-1">
            {jobs.length} job(s) • Updates every 30s
          </p>
        </div>
        <button
          onClick={fetchJobs}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-4 overflow-x-auto">
        {(['all', 'queued', 'running', 'completed', 'failed'] as const).map((status) => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors whitespace-nowrap ${
              filter === status
                ? 'bg-green-600 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      {/* Jobs List */}
      {jobs.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg mb-2">No jobs found</p>
          <p className="text-sm">Jobs will appear here when scheduled</p>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xl">{getStatusIcon(job.status)}</span>
                  <div>
                    <p className="font-medium text-gray-900">
                      {getJobTypeLabel(job.type)}
                    </p>
                    <p className="text-xs text-gray-500">Job #{job.id}</p>
                  </div>
                </div>
                <span className={`px-3 py-1 text-xs font-medium rounded-full border ${getStatusColor(job.status)}`}>
                  {job.status}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-gray-600">Scheduled</p>
                  <p className="font-medium text-gray-900">
                    {format(parseISO(job.scheduled_for), 'MMM d, HH:mm')}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatDistanceToNow(parseISO(job.scheduled_for), { addSuffix: true })}
                  </p>
                </div>

                {job.carbon_intensity && (
                  <div>
                    <p className="text-gray-600">Carbon</p>
                    <div className="mt-1">
                      {getCarbonBadge(job.carbon_intensity)}
                    </div>
                  </div>
                )}

                {job.carbon_score && (
                  <div>
                    <p className="text-gray-600">Eco Score</p>
                    <p className="font-medium text-green-700">
                      {(job.carbon_score * 100).toFixed(0)}%
                    </p>
                  </div>
                )}

                {job.duration_seconds && (
                  <div>
                    <p className="text-gray-600">Duration</p>
                    <p className="font-medium text-gray-900">
                      {Math.floor(job.duration_seconds / 60)}m {job.duration_seconds % 60}s
                    </p>
                  </div>
                )}

                {job.status === 'running' && job.started_at && (
                  <div>
                    <p className="text-gray-600">Running</p>
                    <p className="font-medium text-yellow-700 animate-pulse">
                      {formatDistanceToNow(parseISO(job.started_at))}
                    </p>
                  </div>
                )}

                {job.status === 'completed' && job.completed_at && (
                  <div>
                    <p className="text-gray-600">Completed</p>
                    <p className="font-medium text-green-700">
                      {formatDistanceToNow(parseISO(job.completed_at), { addSuffix: true })}
                    </p>
                  </div>
                )}
              </div>

              {job.error_message && (
                <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                  <span className="font-medium">Error:</span> {job.error_message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
