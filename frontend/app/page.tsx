'use client';

import { useState } from 'react';
import EcoTimeline from '@/components/EcoTimeline';
import CarbonAnalytics from '@/components/CarbonAnalytics';
import JobQueue from '@/components/JobQueue';
import CurrentCarbonIndicator from '@/components/CurrentCarbonIndicator';

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'analytics' | 'jobs'>('overview');

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Current Carbon Intensity Banner */}
        <div className="mb-6">
          <CurrentCarbonIndicator />
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex gap-4">
              <button
                onClick={() => setActiveTab('overview')}
                className={`py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'overview'
                    ? 'border-green-600 text-green-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                Overview
              </button>
              <button
                onClick={() => setActiveTab('analytics')}
                className={`py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'analytics'
                    ? 'border-green-600 text-green-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                Carbon Analytics
              </button>
              <button
                onClick={() => setActiveTab('jobs')}
                className={`py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'jobs'
                    ? 'border-green-600 text-green-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                Job Queue
              </button>
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Timeline */}
            <EcoTimeline hoursAhead={72} />

            {/* Quick Stats Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Mini Analytics */}
              <div className="lg:col-span-2">
                <CarbonAnalytics days={7} />
              </div>

              {/* Recent Jobs */}
              <div className="lg:col-span-2">
                <JobQueue limit={10} />
              </div>
            </div>
          </div>
        )}

        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <CarbonAnalytics days={30} />

            {/* Additional Info Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Our Mission</h3>
                <p className="text-sm text-gray-600">
                  Reduce the carbon footprint of AI training by intelligently scheduling compute-intensive tasks during periods of low grid carbon intensity.
                </p>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">How It Works</h3>
                <p className="text-sm text-gray-600">
                  We fetch real-time carbon intensity forecasts and identify "green windows" - optimal times when renewable energy usage is high and grid emissions are low.
                </p>
              </div>

              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Your Impact</h3>
                <p className="text-sm text-gray-600">
                  Every job scheduled during a green window contributes to a cleaner grid and helps accelerate the transition to 100% renewable energy.
                </p>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'jobs' && (
          <div className="space-y-6">
            <JobQueue limit={50} autoRefresh={true} />

            {/* Job Types Info */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Available Job Types</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="font-medium text-blue-900">RETRAIN_MODEL</p>
                  <p className="text-sm text-blue-700 mt-1">Weekly ML model retraining (~30 min)</p>
                </div>
                <div className="p-3 bg-purple-50 rounded-lg">
                  <p className="font-medium text-purple-900">GENERATE_CONTENT</p>
                  <p className="text-sm text-purple-700 mt-1">AI-powered content creation (~15 min)</p>
                </div>
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="font-medium text-green-900">SYNC_POSTS</p>
                  <p className="text-sm text-green-700 mt-1">Sync Instagram posts (~10 min)</p>
                </div>
                <div className="p-3 bg-yellow-50 rounded-lg">
                  <p className="font-medium text-yellow-900">POST_CONTENT</p>
                  <p className="text-sm text-yellow-700 mt-1">Publish scheduled content (~5 min)</p>
                </div>
                <div className="p-3 bg-indigo-50 rounded-lg">
                  <p className="font-medium text-indigo-900">FETCH_CARBON_FORECAST</p>
                  <p className="text-sm text-indigo-700 mt-1">Update carbon forecasts (~5 min)</p>
                </div>
                <div className="p-3 bg-pink-50 rounded-lg">
                  <p className="font-medium text-pink-900">CALCULATE_ENGAGEMENT</p>
                  <p className="text-sm text-pink-700 mt-1">Analyze post metrics (~10 min)</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Phase 2: Carbon-Aware Job Scheduling • Built with Next.js 14 & FastAPI
            </p>
            <div className="flex items-center gap-4 text-sm text-gray-600">
              <span>Powered by ElectricityMap API</span>
              <span>•</span>
              <span>Region: AU-VIC</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
