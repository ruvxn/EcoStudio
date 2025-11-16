'use client';

import { useState, useEffect } from 'react';
import {
  accountsAPI,
  scheduledPostsAPI,
  workflowAPI,
  type SocialAccount,
  type ScheduledPost,
  type WorkflowStatus,
} from '@/lib/api';
import { format } from 'date-fns';

export default function ContentPage() {
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<SocialAccount | null>(null);
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus | null>(null);
  const [posts, setPosts] = useState<ScheduledPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'pending' | 'generated' | 'approved' | 'posted'>('generated');
  const [creating, setCreating] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [editingPost, setEditingPost] = useState<ScheduledPost | null>(null);
  const [editContent, setEditContent] = useState('');
  const [generating, setGenerating] = useState<number | null>(null);
  const [generatingImage, setGeneratingImage] = useState<number | null>(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  useEffect(() => {
    if (selectedAccount) {
      loadWorkflowStatus();
      loadPosts();
    }
  }, [selectedAccount, activeTab]);

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

  const loadWorkflowStatus = async () => {
    if (!selectedAccount) return;
    try {
      const data = await workflowAPI.status(selectedAccount.id);
      setWorkflowStatus(data);
    } catch (error) {
      console.error('Failed to load workflow status:', error);
    }
  };

  const loadPosts = async () => {
    if (!selectedAccount) return;
    try {
      const statusFilter = activeTab === 'pending' ? 'PENDING' : activeTab.toUpperCase();
      const { posts } = await scheduledPostsAPI.list({
        account_id: selectedAccount.id,
        status: statusFilter,
        page_size: 50,
      });
      setPosts(posts);
    } catch (error) {
      console.error('Failed to load posts:', error);
    }
  };

  const handleCreateWeeklyPlan = async () => {
    if (!selectedAccount || !confirm('Create a 7-day scheduled content plan for this account?')) return;

    setCreating(true);
    try {
      const result = await workflowAPI.createWeeklyPlan({
        account_id: selectedAccount.id,
        num_posts: 7,
        auto_generate: true,
        content_type: 'IMAGE',
      });
      setMessage({
        type: 'success',
        text: `Weekly plan scheduled. ${result.summary.total_posts_scheduled} posts lined up with ${result.summary.generation_jobs_created} automation tasks.`,
      });
      await loadWorkflowStatus();
      await loadPosts();
    } catch (error: any) {
      console.error('Failed to create plan:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to create weekly plan' });
    } finally {
      setCreating(false);
    }
  };

  const handleApprove = async (postId: number) => {
    try {
      await scheduledPostsAPI.update(postId, { user_approved: true });
      setMessage({ type: 'success', text: 'Post approved. It will be published at the scheduled time.' });
      await loadWorkflowStatus();
      await loadPosts();
    } catch (error) {
      console.error('Failed to approve post:', error);
      setMessage({ type: 'error', text: 'Failed to approve post' });
    }
  };

  const handleBulkApprove = async () => {
    if (!selectedAccount || !confirm('Approve all generated content?')) return;

    try {
      const result = await workflowAPI.bulkApprove(selectedAccount.id);
      setMessage({
        type: 'success',
        text: `Approved ${result.approved_count} posts. They will be published at their scheduled times.`,
      });
      await loadWorkflowStatus();
      await loadPosts();
    } catch (error: any) {
      console.error('Failed to bulk approve:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to bulk approve' });
    }
  };

  const handleRegenerate = async (postId: number) => {
    try {
      await scheduledPostsAPI.regenerate(postId);
      setMessage({ type: 'success', text: 'Content refreshed successfully.' });
      await loadPosts();
    } catch (error: any) {
      console.error('Failed to regenerate:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to regenerate content' });
    }
  };

  const handleStartEdit = (post: ScheduledPost) => {
    setEditingPost(post);
    setEditContent(post.content || '');
  };

  const handleSaveEdit = async () => {
    if (!editingPost) return;

    try {
      await scheduledPostsAPI.update(editingPost.id, { content: editContent });
      setMessage({ type: 'success', text: 'Content updated successfully.' });
      setEditingPost(null);
      await loadPosts();
    } catch (error) {
      console.error('Failed to save edit:', error);
      setMessage({ type: 'error', text: 'Failed to save changes' });
    }
  };

  const handleDelete = async (postId: number) => {
    try {
      await scheduledPostsAPI.delete(postId);
      setMessage({ type: 'success', text: 'Post deleted successfully.' });
      await loadWorkflowStatus();
      await loadPosts();
    } catch (error) {
      console.error('Failed to delete post:', error);
      setMessage({ type: 'error', text: 'Failed to delete post' });
    }
  };

  const handlePublishNow = async (postId: number) => {
    try {
      const result = await scheduledPostsAPI.publishNow(postId);
      setMessage({
        type: 'success',
        text: `Post published successfully. View it at: ${result.permalink}`,
      });
      await loadWorkflowStatus();
      await loadPosts();
    } catch (error: any) {
      console.error('Failed to publish:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to publish post' });
    }
  };

  const handleForceGenerate = async (postId: number) => {
    setGenerating(postId);
    try {
      const result = await workflowAPI.forceGenerate(postId);
      setMessage({
        type: 'success',
        text: `Content generated in ${result.generation_time}s. ${result.tokens_used} tokens used.`,
      });
      await loadWorkflowStatus();
      await loadPosts();
    } catch (error: any) {
      console.error('Failed to force generate:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to generate content' });
    } finally {
      setGenerating(null);
    }
  };

  const handleGenerateImage = async (postId: number, regenerate: boolean = false) => {
    setGeneratingImage(postId);
    try {
      const result = await scheduledPostsAPI.generateImage(postId, 'realistic', regenerate);
      setMessage({
        type: 'success',
        text: `Image generated in ${result.generation_time}s`,
      });
      await loadPosts();
    } catch (error: any) {
      console.error('Failed to generate image:', error);
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Failed to generate image' });
    } finally {
      setGeneratingImage(null);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      PENDING: 'bg-gray-100 text-gray-800',
      GENERATED: 'bg-blue-100 text-blue-800',
      APPROVED: 'bg-green-100 text-green-800',
      POSTED: 'bg-purple-100 text-purple-800',
      FAILED: 'bg-red-100 text-red-800',
    };
    return styles[status as keyof typeof styles] || 'bg-gray-100 text-gray-800';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading content...</p>
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
        {/* Page Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Content Management</h1>
              <p className="mt-2 text-gray-600">Plan, review, and schedule upcoming content</p>
            </div>
            <div className="flex items-center gap-3">
              <select
                value={selectedAccount?.id || ''}
                onChange={(e) => {
                  const account = accounts.find((a) => a.id === parseInt(e.target.value));
                  setSelectedAccount(account || null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-600 focus:border-transparent"
              >
                {accounts.map((account) => (
                  <option key={account.id} value={account.id}>
                    @{account.username}
                  </option>
                ))}
              </select>
              <button
                onClick={handleCreateWeeklyPlan}
                disabled={creating}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {creating ? 'Creating...' : 'Create Weekly Plan'}
              </button>
            </div>
          </div>
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

        {/* Workflow Status Cards */}
        {workflowStatus && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-600 mb-1">Pending</p>
              <p className="text-2xl font-bold text-gray-900">{workflowStatus.pending}</p>
            </div>
            <div className="bg-blue-50 rounded-lg border border-blue-200 p-4">
              <p className="text-sm text-blue-900 mb-1">Generated</p>
              <p className="text-2xl font-bold text-blue-900">{workflowStatus.generated}</p>
            </div>
            <div className="bg-green-50 rounded-lg border border-green-200 p-4">
              <p className="text-sm text-green-900 mb-1">Approved</p>
              <p className="text-2xl font-bold text-green-900">{workflowStatus.approved}</p>
            </div>
            <div className="bg-purple-50 rounded-lg border border-purple-200 p-4">
              <p className="text-sm text-purple-900 mb-1">Posted</p>
              <p className="text-2xl font-bold text-purple-900">{workflowStatus.posted}</p>
            </div>
            <div className="bg-red-50 rounded-lg border border-red-200 p-4">
              <p className="text-sm text-red-900 mb-1">Failed</p>
              <p className="text-2xl font-bold text-red-900">{workflowStatus.failed}</p>
            </div>
          </div>
        )}

        {/* Bulk Actions */}
        {activeTab === 'generated' && posts.length > 0 && (
          <div className="mb-6 flex items-center justify-between bg-blue-50 rounded-lg p-4">
            <p className="text-blue-900">
              <strong>{posts.length}</strong> posts awaiting approval
            </p>
            <button
              onClick={handleBulkApprove}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Approve All
            </button>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex gap-4">
              {['generated', 'approved', 'posted', 'pending'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab as any)}
                  className={`py-4 px-6 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab
                      ? 'border-green-600 text-green-600'
                      : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Posts List */}
        {posts.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <p className="text-gray-600">No posts in this category</p>
          </div>
        ) : (
          <div className="space-y-4">
            {posts.map((post) => (
              <div key={post.id} className="bg-white rounded-lg border border-gray-200 p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusBadge(post.status)}`}>
                        {post.status}
                      </span>
                      <span className="text-sm text-gray-600">
                        {format(new Date(post.scheduled_time), 'MMM d, yyyy h:mm a')}
                      </span>
                      {post.predicted_engagement && (
                        <span className="text-sm text-gray-600">
                          Predicted engagement {(post.predicted_engagement * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    {post.status === 'PENDING' && (
                      <div className="text-xs space-y-1">
                        {post.generation_scheduled_for && (
                          <div className="text-green-700 bg-green-50 px-2 py-1 rounded inline-block">
                            Content generation scheduled for {format(new Date(post.generation_scheduled_for), 'MMM d, h:mm a')}
                            {post.green_window_start && ' (green window)'}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {post.status === 'PENDING' && (
                      <button
                        onClick={() => handleForceGenerate(post.id)}
                        disabled={generating === post.id}
                        className="px-3 py-1 text-sm bg-orange-600 text-white rounded hover:bg-orange-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {generating === post.id ? 'Generating...' : 'Generate Now'}
                      </button>
                    )}
                    {post.status === 'GENERATED' && (
                      <>
                        <button
                          onClick={() => handleGenerateImage(post.id, !!post.image_url)}
                          disabled={generatingImage === post.id}
                          className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors disabled:opacity-50"
                          title={post.image_url ? 'Regenerate image' : 'Generate image'}
                        >
                          {generatingImage === post.id ? 'Generating...' : post.image_url ? 'Regenerate' : 'Generate Image'}
                        </button>
                        <button
                          onClick={() => handleStartEdit(post)}
                          className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleRegenerate(post.id)}
                          className="px-3 py-1 text-sm text-purple-600 hover:bg-purple-50 rounded transition-colors"
                        >
                          Regenerate
                        </button>
                        <button
                          onClick={() => handleApprove(post.id)}
                          className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                        >
                          Approve
                        </button>
                      </>
                    )}
                    {post.status === 'APPROVED' && (
                      <button
                        onClick={() => handlePublishNow(post.id)}
                        className="px-3 py-1 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
                      >
                        Publish Now
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(post.id)}
                      className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>

                {/* Generated Image Preview */}
                {post.image_url && (
                  <div className="mb-4">
                    <img
                      src={post.image_url}
                      alt="Generated post image"
                      className="w-full max-w-md rounded-lg shadow-md"
                    />
                  </div>
                )}

                <div className="bg-gray-50 rounded-lg p-4">
                  {editingPost?.id === post.id ? (
                    <div>
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-600 focus:border-transparent"
                        rows={6}
                      />
                      <div className="mt-3 flex items-center gap-2">
                        <button
                          onClick={handleSaveEdit}
                          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                        >
                          Save Changes
                        </button>
                        <button
                          onClick={() => setEditingPost(null)}
                          className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className="text-gray-900 whitespace-pre-wrap">{post.content || 'No content generated yet'}</p>
                  )}
                </div>

                {post.posted_at && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <p className="text-sm text-gray-600">
                      Posted on {format(new Date(post.posted_at), 'MMM d, yyyy h:mm a')}
                      {post.platform_post_id && (
                        <a
                          href={`https://www.instagram.com/p/${post.platform_post_id}/`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-2 text-blue-600 hover:underline"
                        >
                          View on Instagram
                        </a>
                      )}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
