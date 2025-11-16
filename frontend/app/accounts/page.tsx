'use client';

import { useState, useEffect } from 'react';
import { accountsAPI, predictionsAPI, type SocialAccount, type AccountStats } from '@/lib/api';

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<SocialAccount | null>(null);
  const [stats, setStats] = useState<AccountStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [training, setTraining] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      loadStats(selectedAccount.id);
    }
  }, [selectedAccount]);

  const loadAccounts = async () => {
    try {
      const data = await accountsAPI.list();
      const validAccounts = data.filter(
        (account) => account.username && account.follower_count && account.follower_count > 0
      );
      setAccounts(validAccounts);
      if (validAccounts.length > 0 && !selectedAccount) {
        setSelectedAccount(validAccounts[0]);
      } else if (validAccounts.length === 0) {
        setSelectedAccount(null);
      }
    } catch (error) {
      console.error('Failed to load accounts:', error);
      setMessage({ type: 'error', text: 'Failed to load accounts' });
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async (accountId: number) => {
    try {
      const data = await accountsAPI.stats(accountId);
      setStats(data);
    } catch (error) {
      console.error('Failed to load stats:', error);
      setStats(null);
    }
  };

  const handleConnect = async () => {
    try {
      const { authorization_url } = await accountsAPI.connect();
      window.location.href = authorization_url;
    } catch (error) {
      console.error('Failed to initiate connection:', error);
      setMessage({ type: 'error', text: 'Failed to connect Instagram account' });
    }
  };

  const handleSync = async () => {
    if (!selectedAccount) return;

    setSyncing(true);
    try {
      const result = await accountsAPI.sync(selectedAccount.id, 90, true);
      setMessage({
        type: 'success',
        text: `Synced ${result.posts_fetched} posts (${result.posts_new} new, ${result.posts_updated} updated)`,
      });
      await loadStats(selectedAccount.id);
    } catch (error) {
      console.error('Failed to sync:', error);
      setMessage({ type: 'error', text: 'Failed to sync posts' });
    } finally {
      setSyncing(false);
    }
  };

  const handleTrain = async () => {
    if (!selectedAccount) return;

    setTraining(true);
    try {
      const result = await predictionsAPI.train(selectedAccount.id);
      setMessage({
        type: 'success',
        text: `Model trained successfully! Accuracy: ${(result.accuracy * 100).toFixed(1)}% (${result.training_samples} samples)`,
      });
    } catch (error: any) {
      console.error('Failed to train model:', error);
      const errorMsg = error.response?.data?.detail || 'Failed to train ML model';
      setMessage({ type: 'error', text: errorMsg });
    } finally {
      setTraining(false);
    }
  };

  const handleDisconnect = async () => {
    if (!selectedAccount || !confirm('Are you sure you want to disconnect this account?')) return;

    try {
      await accountsAPI.disconnect(selectedAccount.id);
      setMessage({ type: 'success', text: 'Account disconnected successfully' });
      setSelectedAccount(null);
      setStats(null);
      await loadAccounts();
    } catch (error) {
      console.error('Failed to disconnect:', error);
      setMessage({ type: 'error', text: 'Failed to disconnect account' });
    }
  };

  const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading accounts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Instagram Accounts</h1>
          <p className="mt-2 text-gray-600">Manage your connected Instagram accounts and train ML models</p>
        </div>

        {/* Message Banner */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
            }`}
          >
            <div className="flex items-center justify-between">
              <p>{message.text}</p>
              <button onClick={() => setMessage(null)} className="text-sm underline">
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Main Content */}
        {accounts.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">No Instagram Account Connected</h2>
            <p className="text-gray-600 mb-6">
              Connect your Instagram Business account to start automating your content strategy
            </p>
            <button
              onClick={handleConnect}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              Connect Instagram Account
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Sidebar - Account List */}
            <div className="lg:col-span-1">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-900">Connected Accounts</h2>
                  <button
                    onClick={handleConnect}
                    className="text-sm text-green-600 hover:text-green-700 font-medium"
                  >
                    + Add
                  </button>
                </div>

                <div className="space-y-2">
                  {accounts.map((account) => (
                    <button
                      key={account.id}
                      onClick={() => setSelectedAccount(account)}
                      className={`w-full p-4 rounded-lg text-left transition-colors ${
                        selectedAccount?.id === account.id
                          ? 'bg-green-50 border-2 border-green-600'
                          : 'bg-gray-50 border-2 border-transparent hover:bg-gray-100'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-white font-semibold">
                          {account.username[0].toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 truncate">@{account.username}</p>
                          <p className="text-sm text-gray-600">{account.follower_count.toLocaleString()} followers</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Main Content - Account Details */}
            <div className="lg:col-span-2 space-y-6">
              {/* Account Info Card */}
              <div className="bg-white rounded-lg border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-white text-2xl font-semibold">
                      {selectedAccount?.username[0].toUpperCase()}
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-gray-900">@{selectedAccount?.username}</h2>
                      <p className="text-gray-600">{selectedAccount?.follower_count.toLocaleString()} followers</p>
                    </div>
                  </div>
                  <button
                    onClick={handleDisconnect}
                    className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    Disconnect
                  </button>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <button
                    onClick={handleSync}
                    disabled={syncing}
                    className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {syncing ? 'Syncing...' : 'Sync Posts'}
                  </button>
                  <button
                    onClick={handleTrain}
                    disabled={training || !stats}
                    className="px-4 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {training ? 'Training...' : 'Train ML Model'}
                  </button>
                  <a
                    href="/content"
                    className="px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors text-center"
                  >
                    View Content
                  </a>
                </div>
              </div>

              {/* Stats Card */}
              {stats ? (
                <div className="bg-white rounded-lg border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Analytics</h3>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Total Posts</p>
                      <p className="text-2xl font-bold text-gray-900">{stats.total_posts}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Avg Engagement</p>
                      <p className="text-2xl font-bold text-gray-900">{(stats.avg_engagement * 100).toFixed(1)}%</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Total Likes</p>
                      <p className="text-2xl font-bold text-gray-900">{stats.total_likes.toLocaleString()}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-600 mb-1">Total Comments</p>
                      <p className="text-2xl font-bold text-gray-900">{stats.total_comments.toLocaleString()}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-blue-50 rounded-lg p-4">
                      <p className="text-sm text-blue-900 font-medium mb-2">Best Posting Time</p>
                      <p className="text-xl font-bold text-blue-900">
                        {stats.best_posting_hour}:00 - {stats.best_posting_hour + 1}:00
                      </p>
                      <p className="text-sm text-blue-700 mt-1">Hour of day with highest engagement</p>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-4">
                      <p className="text-sm text-purple-900 font-medium mb-2">Best Posting Day</p>
                      <p className="text-xl font-bold text-purple-900">{dayNames[stats.best_posting_day]}</p>
                      <p className="text-sm text-purple-700 mt-1">Day of week with highest engagement</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
                  <p className="text-gray-600">No analytics available. Sync posts to view stats.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
