'use client';

import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { jobsAPI, CarbonAnalyticsResponse } from '@/lib/api';
import { format, parseISO } from 'date-fns';

interface CarbonAnalyticsProps {
  days?: number;
}

export default function CarbonAnalytics({ days = 30 }: CarbonAnalyticsProps) {
  const [analytics, setAnalytics] = useState<CarbonAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPeriod, setSelectedPeriod] = useState(days);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        const data = await jobsAPI.getCarbonAnalytics(selectedPeriod);
        setAnalytics(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching carbon analytics:', err);
        setError('Failed to load analytics');
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
    // Refresh every 10 minutes
    const interval = setInterval(fetchAnalytics, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [selectedPeriod]);

  if (loading) {
    return (
      <div className="w-full bg-white rounded-lg border border-gray-200 p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
          <div className="h-64 bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (error || !analytics) {
    return (
      <div className="w-full bg-white rounded-lg border border-red-200 p-6">
        <div className="text-center text-red-600">
          <svg className="w-12 h-12 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="font-medium">{error || 'Failed to load analytics'}</p>
        </div>
      </div>
    );
  }

  const { summary, daily_breakdown } = analytics;

  // Transform daily breakdown for chart
  const chartData = [...daily_breakdown].reverse().map((day) => ({
    date: format(parseISO(day.date), 'MMM d'),
    savedGrams: day.saved_grams,
    savedKg: (day.saved_grams / 1000).toFixed(2),
    jobCount: day.job_count,
  }));

  // Calculate equivalent environmental impact
  const treesEquivalent = (summary.total_carbon_saved_kg / 20).toFixed(1); // ~20kg CO2 per tree per year
  const milesNotDriven = (summary.total_carbon_saved_kg / 0.404).toFixed(0); // ~404g CO2 per mile

  const MetricCard = ({ title, value, unit, trend, color = 'green' }: {
    title: string;
    value: string | number;
    unit: string;
    trend?: string;
    color?: 'green' | 'blue' | 'purple' | 'orange';
  }) => {
    const colorClasses = {
      green: 'bg-green-50 border-green-200 text-green-700',
      blue: 'bg-blue-50 border-blue-200 text-blue-700',
      purple: 'bg-purple-50 border-purple-200 text-purple-700',
      orange: 'bg-orange-50 border-orange-200 text-orange-700',
    };

    return (
      <div className={`rounded-lg border p-4 ${colorClasses[color]}`}>
        <div className="flex items-center justify-between mb-2">
          {trend && <span className="text-xs font-medium">{trend}</span>}
        </div>
        <p className="text-sm font-medium opacity-80">{title}</p>
        <div className="flex items-baseline gap-1 mt-1">
          <p className="text-2xl font-bold">{value}</p>
          <p className="text-sm font-medium opacity-70">{unit}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="w-full bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Carbon Savings Analytics</h2>
          <p className="text-sm text-gray-600 mt-1">
            Environmental impact of eco-scheduling
          </p>
        </div>
        <select
          value={selectedPeriod}
          onChange={(e) => setSelectedPeriod(Number(e.target.value))}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-green-500 focus:border-transparent"
        >
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="Total CO₂ Saved"
          value={summary.total_carbon_saved_kg}
          unit="kg"
          color="green"
        />
        <MetricCard
          title="Jobs Optimized"
          value={summary.total_jobs}
          unit="jobs"
          color="blue"
        />
        <MetricCard
          title="Avg Savings Per Job"
          value={summary.avg_saved_per_job_grams.toFixed(0)}
          unit="grams"
          color="purple"
        />
        <MetricCard
          title="Energy Optimized"
          value={summary.total_energy_kwh.toFixed(1)}
          unit="kWh"
          color="orange"
        />
      </div>

      {/* Environmental Impact */}
      <div className="mb-6 p-4 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-200">
        <p className="text-sm font-semibold text-green-900 mb-2">Environmental Impact</p>
        <div className="grid grid-cols-2 gap-4 text-sm text-green-800">
          <div>
            <span className="font-medium">Equivalent to:</span>
            <p className="mt-1"><strong>{treesEquivalent}</strong> trees planted</p>
          </div>
          <div>
            <span className="font-medium">Same as:</span>
            <p className="mt-1"><strong>{milesNotDriven}</strong> miles not driven</p>
          </div>
        </div>
      </div>

      {/* Daily Breakdown Chart */}
      {chartData.length > 0 ? (
        <>
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Daily Carbon Savings</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
              />
              <YAxis
                label={{ value: 'CO₂ Saved (grams)', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }}
                tick={{ fontSize: 12 }}
                stroke="#6b7280"
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-white p-3 rounded-lg shadow-lg border border-gray-200">
                        <p className="font-semibold text-gray-900">{data.date}</p>
                        <p className="text-sm mt-1">
                          <span className="font-medium text-green-700">Saved:</span>{' '}
                          {data.savedGrams} g ({data.savedKg} kg)
                        </p>
                        <p className="text-sm">
                          <span className="font-medium text-blue-700">Jobs:</span>{' '}
                          {data.jobCount}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Legend />
              <Bar
                dataKey="savedGrams"
                fill="#10b981"
                name="CO₂ Saved (grams)"
                radius={[8, 8, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </>
      ) : (
        <div className="text-center py-12 text-gray-500">
          <p className="text-lg mb-2">No data yet</p>
          <p className="text-sm">Carbon savings will appear here once jobs are executed</p>
        </div>
      )}
    </div>
  );
}
