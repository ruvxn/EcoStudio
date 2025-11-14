'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, Area, ComposedChart, Scatter } from 'recharts';
import { carbonAPI, jobsAPI, ForecastDataPoint, Job } from '@/lib/api';
import { format, parseISO } from 'date-fns';

interface EcoTimelineProps {
  hoursAhead?: number;
}

export default function EcoTimeline({ hoursAhead = 72 }: EcoTimelineProps) {
  const [forecastData, setForecastData] = useState<ForecastDataPoint[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Fetch carbon forecast
        const forecastResponse = await carbonAPI.getForecast(hoursAhead);
        setForecastData(forecastResponse.data);

        // Fetch scheduled jobs
        const jobsResponse = await jobsAPI.getJobs({
          status: 'queued',
          limit: 100
        });
        setJobs(jobsResponse.jobs);

        setError(null);
      } catch (err) {
        console.error('Error fetching timeline data:', err);
        setError('Failed to load timeline data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    // Refresh every 5 minutes
    const interval = setInterval(fetchData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [hoursAhead]);

  if (loading) {
    return (
      <div className="w-full h-96 flex items-center justify-center bg-white rounded-lg border border-gray-200">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading timeline...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-96 flex items-center justify-center bg-white rounded-lg border border-red-200">
        <div className="text-center text-red-600">
          <svg className="w-12 h-12 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p className="font-medium">{error}</p>
        </div>
      </div>
    );
  }

  // Transform data for chart
  const chartData = forecastData.map((point) => {
    const timestamp = new Date(point.time).getTime();

    // Find jobs scheduled at this time
    const scheduledJobs = jobs.filter((job) => {
      const jobTime = new Date(job.scheduled_for).getTime();
      // Match jobs within 30-minute window
      return Math.abs(jobTime - timestamp) < 30 * 60 * 1000;
    });

    return {
      time: point.time,
      intensity: point.intensity,
      is_green: point.is_green,
      is_renewable_high: point.is_renewable_high,
      jobs: scheduledJobs.length,
      // Add job markers for scatter plot
      jobMarker: scheduledJobs.length > 0 ? point.intensity : null,
    };
  });

  const greenThreshold = 300;
  const mediumThreshold = 500;

  // Custom tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const time = parseISO(data.time);

      return (
        <div className="bg-white p-4 rounded-lg shadow-lg border border-gray-200">
          <p className="font-semibold text-gray-900">{format(time, 'MMM d, HH:mm')}</p>
          <p className="text-sm mt-1">
            <span className="font-medium">Carbon Intensity:</span>{' '}
            <span className={`font-semibold ${
              data.intensity < greenThreshold ? 'text-green-600' :
              data.intensity < mediumThreshold ? 'text-yellow-600' : 'text-red-600'
            }`}>
              {data.intensity} gCO₂/kWh
            </span>
          </p>
          {data.is_renewable_high && (
            <p className="text-xs text-green-600 mt-1">High renewable energy</p>
          )}
          {data.jobs > 0 && (
            <p className="text-xs text-blue-600 mt-1">{data.jobs} job(s) scheduled</p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="w-full bg-white rounded-lg border border-gray-200 p-6">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900">Carbon Intensity Timeline</h2>
        <p className="text-sm text-gray-600 mt-1">
          Next {hoursAhead} hours • Green zones show optimal scheduling windows
        </p>
      </div>

      <div className="mb-4 flex items-center gap-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-green-100 border border-green-500 rounded"></div>
          <span className="text-gray-700">Low (&lt; {greenThreshold})</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-yellow-100 border border-yellow-500 rounded"></div>
          <span className="text-gray-700">Medium ({greenThreshold}-{mediumThreshold})</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 bg-red-100 border border-red-500 rounded"></div>
          <span className="text-gray-700">High (&gt; {mediumThreshold})</span>
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <div className="w-3 h-3 bg-blue-600 rounded-full"></div>
          <span className="text-gray-700">Scheduled Jobs</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={400}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorIntensity" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.1} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
          <XAxis
            dataKey="time"
            tickFormatter={(time) => format(parseISO(time), 'MMM d HH:mm')}
            tick={{ fontSize: 12 }}
            stroke="#6b7280"
          />
          <YAxis
            label={{ value: 'gCO₂/kWh', angle: -90, position: 'insideLeft', style: { fontSize: 12 } }}
            tick={{ fontSize: 12 }}
            stroke="#6b7280"
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend />

          {/* Green threshold line */}
          <ReferenceLine
            y={greenThreshold}
            stroke="#10b981"
            strokeDasharray="3 3"
            label={{ value: 'Green', fill: '#10b981', fontSize: 11 }}
          />

          {/* Medium threshold line */}
          <ReferenceLine
            y={mediumThreshold}
            stroke="#f59e0b"
            strokeDasharray="3 3"
            label={{ value: 'Medium', fill: '#f59e0b', fontSize: 11 }}
          />

          {/* Carbon intensity area */}
          <Area
            type="monotone"
            dataKey="intensity"
            fill="url(#colorIntensity)"
            stroke="none"
          />

          {/* Carbon intensity line */}
          <Line
            type="monotone"
            dataKey="intensity"
            stroke="#10b981"
            strokeWidth={2}
            dot={false}
            name="Carbon Intensity"
            activeDot={{ r: 6 }}
          />

          {/* Job markers */}
          <Scatter
            dataKey="jobMarker"
            fill="#2563eb"
            name="Scheduled Jobs"
            shape="circle"
          />
        </ComposedChart>
      </ResponsiveContainer>

      {jobs.length > 0 && (
        <div className="mt-4 p-3 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-900">
            <span className="font-semibold">{jobs.length} job(s)</span> scheduled in the next {hoursAhead} hours
          </p>
        </div>
      )}
    </div>
  );
}
