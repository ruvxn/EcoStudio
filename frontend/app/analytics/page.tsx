'use client';

import { useState, useEffect } from 'react';
import { accountsAPI, predictionsAPI, type SocialAccount, type AccountStats, type PredictionSchedule } from '@/lib/api';
import { format } from 'date-fns';

export default function AnalyticsPage() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<SocialAccount | null>(null);
  const [stats, setStats] = useState<AccountStats | null>(null);
  const [predictionSchedule, setPredictionSchedule] = useState<PredictionSchedule | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      loadStats();
      loadPredictions();
    }
  }, [selectedAccount]);

  const loadAccounts = async () => {
    try {
      const data = await accountsAPI.list();
      setAccounts(data);
      if (data.length > 0 && !selectedAccount) {
        setSelectedAccount(data[0]);
      }
    } catch (error) {
      console.error('Failed to load accounts:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    if (!selectedAccount) return;
    try {
      const data = await accountsAPI.stats(selectedAccount.id);
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  };

  const loadPredictions = async () => {
    if (!selectedAccount) return;
    try {
      const data = await predictionsAPI.latest(selectedAccount.id);
      setPredictionSchedule(data);
    } catch (error) {
      console.error('Failed to load predictions:', error);
      setPredictionSchedule(null);
    }
  };

  const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (accounts.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-4">No Instagram account connected</p>
          <a href="/accounts" className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700">
            Connect Account
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Analytics & Predictions</h1>
              <p className="mt-2 text-gray-600">ML-powered insights for optimal posting strategy</p>
            </div>
            <select
              value={selectedAccount?.id || ''}
              onChange={(e) => {
                const account = accounts.find((a) => a.id === parseInt(e.target.value));
                setSelectedAccount(account || null);
              }}
              className="px-4 py-2 border border-gray-300 rounded-lg"
            >
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  @{account.username}
                </option>
              ))}
            </select>
          </div>
        </div>

        {stats ? (
          <>
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
              <h2 className="text-xl font-semibold text-gray-900 mb-6">Performance Overview</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm text-blue-900 mb-1">Total Posts</p>
                  <p className="text-3xl font-bold text-blue-900">{stats.total_posts}</p>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <p className="text-sm text-purple-900 mb-1">Avg Engagement</p>
                  <p className="text-3xl font-bold text-purple-900">{(stats.avg_engagement * 100).toFixed(1)}%</p>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <p className="text-sm text-green-900 mb-1">Total Likes</p>
                  <p className="text-3xl font-bold text-green-900">{stats.total_likes.toLocaleString()}</p>
                </div>
                <div className="bg-pink-50 rounded-lg p-4">
                  <p className="text-sm text-pink-900 mb-1">Total Comments</p>
                  <p className="text-3xl font-bold text-pink-900">{stats.total_comments.toLocaleString()}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-blue-900 mb-3">Best Posting Time</h3>
                  <div className="text-4xl font-bold text-blue-900 mb-2">
                    {stats.best_posting_hour}:00 - {stats.best_posting_hour + 1}:00
                  </div>
                  <p className="text-blue-800">Peak engagement window</p>
                </div>

                <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-purple-900 mb-3">Best Posting Day</h3>
                  <div className="text-4xl font-bold text-purple-900 mb-2">{dayNames[stats.best_posting_day]}</div>
                  <p className="text-purple-800">Highest engagement day</p>
                </div>
              </div>
            </div>

            {predictionSchedule && predictionSchedule.predictions.length > 0 ? (
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-6">ML-Predicted Optimal Times</h2>
                <div className="mb-4 p-4 bg-blue-50 rounded-lg">
                  <p className="text-sm text-blue-900">
                    <strong>Date Range:</strong> {format(new Date(predictionSchedule.date_range_start), 'MMM d')} - {format(new Date(predictionSchedule.date_range_end), 'MMM d, yyyy')}
                  </p>
                  <p className="text-sm text-blue-900 mt-1">
                    <strong>Average Predicted Engagement:</strong> {(predictionSchedule.avg_predicted_engagement * 100).toFixed(1)}%
                  </p>
                  <p className="text-sm text-blue-900 mt-1">
                    <strong>Model Version:</strong> {predictionSchedule.model_version}
                  </p>
                </div>
                <div className="space-y-3">
                  {predictionSchedule.predictions.map((prediction, idx) => (
                    <div key={prediction.id} className="flex items-center justify-between bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-green-600 text-white rounded-full flex items-center justify-center font-bold">
                          #{idx + 1}
                        </div>
                        <div>
                          <p className="font-semibold text-gray-900">
                            {prediction.day_name}, {format(new Date(prediction.prediction_date), 'MMMM d, yyyy')}
                          </p>
                          <p className="text-sm text-gray-600">
                            {prediction.hour}:00 - {prediction.hour + 1}:00
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-bold text-green-600">
                          {(prediction.predicted_engagement * 100).toFixed(1)}%
                        </p>
                        <p className="text-xs text-gray-500">
                          Confidence: {(prediction.confidence_score * 100).toFixed(0)}% ({prediction.confidence_level})
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
                <p className="text-gray-600 mb-4">No ML predictions available</p>
                <a href="/accounts" className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 inline-block">
                  Train ML Model
                </a>
              </div>
            )}
          </>
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <p className="text-gray-600 mb-4">No analytics data. Sync posts first.</p>
            <a href="/accounts" className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 inline-block">
              Go to Accounts
            </a>
          </div>
        )}
      </main>
    </div>
  );
}
