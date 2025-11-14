'use client';

import { useEffect, useState } from 'react';
import { carbonAPI, CarbonIntensity } from '@/lib/api';

export default function CurrentCarbonIndicator() {
  const [current, setCurrent] = useState<CarbonIntensity | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCurrent = async () => {
      try {
        const data = await carbonAPI.getCurrentIntensity();
        setCurrent(data);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching current carbon intensity:', err);
        setLoading(false);
      }
    };

    fetchCurrent();
    // Refresh every 5 minutes
    const interval = setInterval(fetchCurrent, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !current) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
        <div className="h-8 bg-gray-200 rounded w-3/4"></div>
      </div>
    );
  }

  const getBgColor = (color: string) => {
    switch (color) {
      case 'green':
        return 'bg-green-50 border-green-300';
      case 'yellow':
        return 'bg-yellow-50 border-yellow-300';
      case 'red':
        return 'bg-red-50 border-red-300';
      default:
        return 'bg-gray-50 border-gray-300';
    }
  };

  const getTextColor = (color: string) => {
    switch (color) {
      case 'green':
        return 'text-green-700';
      case 'yellow':
        return 'text-yellow-700';
      case 'red':
        return 'text-red-700';
      default:
        return 'text-gray-700';
    }
  };

  const getIcon = (category: string) => {
    const iconClasses = "w-8 h-8";
    switch (category) {
      case 'low':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        );
      case 'medium':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        );
      case 'high':
        return (
          <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
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

  return (
    <div className={`rounded-lg border-2 p-4 ${getBgColor(current.color)}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600">Current Carbon Intensity</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-3xl">{getIcon(current.category)}</span>
            <p className={`text-3xl font-bold ${getTextColor(current.color)}`}>
              {current.intensity}
            </p>
            <span className={`text-sm font-medium ${getTextColor(current.color)}`}>
              {current.unit}
            </span>
          </div>
        </div>
        <div className="text-right">
          <span className={`inline-block px-3 py-1 text-sm font-semibold rounded-full ${
            current.color === 'green' ? 'bg-green-200 text-green-800' :
            current.color === 'yellow' ? 'bg-yellow-200 text-yellow-800' :
            'bg-red-200 text-red-800'
          }`}>
            {current.category.toUpperCase()}
          </span>
          <p className="text-xs text-gray-600 mt-2">
            {current.category === 'low' && 'Great time to schedule jobs!'}
            {current.category === 'medium' && 'Moderate carbon intensity'}
            {current.category === 'high' && 'Consider waiting for greener time'}
          </p>
        </div>
      </div>
    </div>
  );
}
