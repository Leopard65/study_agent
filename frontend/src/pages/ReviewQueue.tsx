import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import LatexRenderer from '../components/LatexRenderer';
import { getReviewQueue, submitReviewAction, getApiErrorMessage } from '../api/client';
import type { ReviewQueueItem, ReviewQueueResponse } from '../api/client';

export default function ReviewQueue() {
  const [data, setData] = useState<ReviewQueueResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [currentIdx, setCurrentIdx] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const [completed, setCompleted] = useState(false);
  // Track items skipped in the frontend (removed from visible queue without DB write)
  const [skippedIds, setSkippedIds] = useState<Set<number>>(new Set());

  const loadQueue = useCallback(() => {
    getReviewQueue()
      .then(r => {
        setData(r);
        setCurrentIdx(0);
        setShowAnswer(false);
        setCompleted(false);
        setSkippedIds(new Set());
        setError('');
      })
      .catch(err => {
        setError(getApiErrorMessage(err, '加载复习队列失败。'));
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => { loadQueue(); }, [loadQueue]);

  // Manual reload: set loading first, then re-fetch
  const handleReload = () => {
    setLoading(true);
    getReviewQueue()
      .then(r => {
        setData(r);
        setCurrentIdx(0);
        setShowAnswer(false);
        setCompleted(false);
        setSkippedIds(new Set());
        setError('');
      })
      .catch(err => {
        setError(getApiErrorMessage(err, '加载复习队列失败。'));
      })
      .finally(() => {
        setLoading(false);
      });
  };

  // Filtered visible items (excluding skipped)
  const visibleItems: ReviewQueueItem[] = data
    ? data.items.filter(it => !skippedIds.has(it.id))
    : [];

  const currentItem: ReviewQueueItem | undefined = visibleItems[currentIdx];
  const progress = visibleItems.length > 0
    ? `${Math.min(currentIdx + 1, visibleItems.length)} / ${visibleItems.length}`
    : '0 / 0';

  const handleAction = async (action: string) => {
    if (!currentItem || actionLoading) return;
    setActionLoading(true);
    setActionError('');
    try {
      await submitReviewAction(currentItem.id, action);

      if (action === 'skip') {
        // Remove from frontend queue only
        setSkippedIds(prev => new Set(prev).add(currentItem.id));
        // Stay on same index (or go to 0 if out of bounds)
        if (currentIdx >= visibleItems.length - 1) {
          // Will be 0 after filtering, check if completed
          if (visibleItems.length <= 1) {
            setCompleted(true);
          }
        }
        setShowAnswer(false);
      } else {
        // For mastered/again/postpone, remove from queue and advance
        setSkippedIds(prev => new Set(prev).add(currentItem.id));
        setShowAnswer(false);

        if (visibleItems.length <= 1) {
          setCompleted(true);
        }
        // Don't increment idx — the item is removed, so same idx points to next
      }
    } catch (err) {
      setActionError(getApiErrorMessage(err, '操作失败，请重试。'));
    } finally {
      setActionLoading(false);
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ' || e.key === 'Enter') {
        if (!showAnswer && currentItem) {
          e.preventDefault();
          setShowAnswer(true);
        }
      }
      if (showAnswer && !actionLoading) {
        if (e.key === '1') { e.preventDefault(); handleAction('mastered'); }
        if (e.key === '2') { e.preventDefault(); handleAction('again'); }
        if (e.key === '3') { e.preventDefault(); handleAction('postpone'); }
        if (e.key === '4') { e.preventDefault(); handleAction('skip'); }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400 dark:text-gray-500">加载中...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-300">
          {error}
          <button onClick={handleReload} className="ml-3 text-sm underline">重试</button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  // Completed state
  if (completed || visibleItems.length === 0) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 dark:text-gray-100">今日复习</h1>
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-8 text-center">
          <div className="text-5xl mb-4">🎉</div>
          <h2 className="text-xl font-semibold mb-2 dark:text-gray-100">
            {data.total_due > 0 ? '本轮复习完成！' : '今日无待复习错题'}
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6">
            {data.total_due > 0
              ? `本轮已处理 ${data.total_due} 道，继续保持！`
              : '所有错题都在掌握中，明天再来吧。'}
          </p>

          {data.weak_points.length > 0 && (
            <div className="mb-6 text-left">
              <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">薄弱知识点</h3>
              <div className="flex flex-wrap gap-2">
                {data.weak_points.map(wp => (
                  <span key={wp.name} className="px-2 py-1 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 rounded text-xs">
                    {wp.name} ({wp.count}题)
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-3 justify-center">
            <Link to="/" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
              返回工作台
            </Link>
            <Link to="/errors" className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 text-sm">
              查看错题本
            </Link>
            {data.total_due > 0 && (
              <button onClick={handleReload} className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 text-sm">
                重新开始
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4 dark:text-gray-100">今日复习</h1>

      {/* Progress bar */}
      <div className="mb-4 flex items-center gap-3">
        <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-300"
            style={{ width: `${((skippedIds.size) / Math.max(data.total_due, 1)) * 100}%` }}
          />
        </div>
        <span className="text-sm text-gray-500 dark:text-gray-400 whitespace-nowrap">{progress}</span>
      </div>

      {/* Action error */}
      {actionError && (
        <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-300">
          {actionError}
        </div>
      )}

      {/* Current question card */}
      {currentItem && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-6">
          {/* Meta badges */}
          <div className="flex flex-wrap gap-2 mb-4">
            {currentItem.subject && (
              <span className="px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded text-xs">{currentItem.subject}</span>
            )}
            {currentItem.knowledge_point && (
              <span className="px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 rounded text-xs">{currentItem.knowledge_point}</span>
            )}
            {currentItem.error_type && (
              <span className="px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded text-xs">{currentItem.error_type}</span>
            )}
            <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded text-xs">
              复习 {currentItem.review_count} 次
            </span>
            {currentItem.due_days > 0 && (
              <span className="px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 rounded text-xs">
                逾期 {currentItem.due_days} 天
              </span>
            )}
            {currentItem.due_days === 0 && (
              <span className="px-2 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 rounded text-xs">今日到期</span>
            )}
          </div>

          {/* Priority reason */}
          {currentItem.priority_reason && (
            <div className="mb-3 text-xs text-gray-400 dark:text-gray-500">
              📌 {currentItem.priority_reason}
            </div>
          )}

          {/* Question */}
          <div className="mb-4">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">题目</div>
            <div className="text-gray-800 dark:text-gray-100 leading-relaxed">
              <LatexRenderer content={currentItem.question} />
            </div>
          </div>

          {/* Show answer button (before expanding) */}
          {!showAnswer && (
            <button
              onClick={() => setShowAnswer(true)}
              className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
              title="快捷键：空格 或 Enter"
            >
              显示解析与答案
            </button>
          )}

          {/* Answer section (after expanding) */}
          {showAnswer && (
            <div className="space-y-4 border-t border-gray-200 dark:border-gray-700 pt-4 mt-2">
              {/* User's wrong answer */}
              {currentItem.user_answer && (
                <div>
                  <div className="text-sm text-red-500 mb-1">❌ 我的错误答案</div>
                  <div className="text-gray-700 dark:text-gray-300 text-sm bg-red-50 dark:bg-red-900/20 rounded p-3">
                    <LatexRenderer content={currentItem.user_answer} />
                  </div>
                </div>
              )}

              {/* Correct answer */}
              {currentItem.correct_answer && (
                <div>
                  <div className="text-sm text-green-600 mb-1">✅ 正确答案</div>
                  <div className="text-gray-700 dark:text-gray-300 text-sm bg-green-50 dark:bg-green-900/20 rounded p-3">
                    <LatexRenderer content={currentItem.correct_answer} />
                  </div>
                </div>
              )}

              {/* Error reason */}
              {currentItem.error_reason && (
                <div>
                  <div className="text-sm text-orange-500 mb-1">💡 错误原因</div>
                  <div className="text-gray-700 dark:text-gray-300 text-sm">
                    <LatexRenderer content={currentItem.error_reason} />
                  </div>
                </div>
              )}

              {/* Correct approach */}
              {currentItem.correct_approach && (
                <div>
                  <div className="text-sm text-blue-500 mb-1">📝 正确思路</div>
                  <div className="text-gray-700 dark:text-gray-300 text-sm">
                    <LatexRenderer content={currentItem.correct_approach} />
                  </div>
                </div>
              )}

              {/* Review suggestion */}
              {currentItem.review_suggestion && (
                <div>
                  <div className="text-sm text-purple-500 mb-1">🎯 复习建议</div>
                  <div className="text-gray-700 dark:text-gray-300 text-sm">
                    <LatexRenderer content={currentItem.review_suggestion} />
                  </div>
                </div>
              )}

              {/* Action buttons — single column on mobile, 2-col on sm+ */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2">
                <button
                  onClick={() => handleAction('mastered')}
                  disabled={actionLoading}
                  className="py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
                  title="快捷键 1"
                >
                  ✅ 标记掌握
                </button>
                <button
                  onClick={() => handleAction('again')}
                  disabled={actionLoading}
                  className="py-2.5 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-50 text-sm font-medium"
                  title="快捷键 2 · 今日仍在复习队列"
                >
                  🔁 仍需复习
                </button>
                <button
                  onClick={() => handleAction('postpone')}
                  disabled={actionLoading}
                  className="py-2.5 bg-gray-500 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 text-sm font-medium"
                  title="快捷键 3 · 明日再复习"
                >
                  ⏭ 明日再来
                </button>
                <button
                  onClick={() => handleAction('skip')}
                  disabled={actionLoading}
                  className="py-2.5 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-400 dark:hover:bg-gray-500 disabled:opacity-50 text-sm font-medium"
                  title="快捷键 4 · 仅本轮跳过"
                >
                  ⏩ 跳过本轮
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Weak points */}
      {data.weak_points.length > 0 && (
        <div className="mt-4 bg-white dark:bg-gray-800 rounded-xl shadow p-4">
          <h3 className="text-sm font-medium text-gray-600 dark:text-gray-300 mb-2">薄弱知识点</h3>
          <div className="flex flex-wrap gap-2">
            {data.weak_points.map(wp => (
              <span key={wp.name} className="px-2 py-1 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-300 rounded text-xs">
                {wp.name} ({wp.count}题)
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
