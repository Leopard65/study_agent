import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { getDashboard, getDashboardTrends, listPlans, updatePlan, getActiveSession, startSession, stopSession, getApiErrorMessage } from '../api/client';
import type { DashboardStats, StudyPlanItem, TrendDay, StudySessionItem } from '../api/client';
import { formatLocalDate } from '../utils/date';
import { useReviewTitle } from '../hooks/useDocumentTitle';

export default function Dashboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [todayPlans, setTodayPlans] = useState<StudyPlanItem[]>([]);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [toggleError, setToggleError] = useState('');

  // Trends
  const [trendDays, setTrendDays] = useState<7 | 30>(7);
  const [trends, setTrends] = useState<TrendDay[]>([]);
  const [trendsLoading, setTrendsLoading] = useState(true);

  // Study session timer
  const [activeSession, setActiveSession] = useState<StudySessionItem | null>(null);
  const [sessionSubject, setSessionSubject] = useState('');
  const [sessionNote, setSessionNote] = useState('');
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState('');
  const [elapsed, setElapsed] = useState(0);

  const today = formatLocalDate();

  const refresh = useCallback(() => {
    getDashboard().then(setStats).catch(() => {});
    listPlans(today).then(setTodayPlans).catch(() => {});
  }, [today]);

  useEffect(() => { refresh(); }, [refresh]);

  // Load active session on mount
  useEffect(() => {
    getActiveSession().then(s => {
      setActiveSession(s);
      if (s?.started_at) {
        const start = new Date(s.started_at).getTime();
        setElapsed(Math.floor((Date.now() - start) / 1000));
      }
    }).catch(() => {});
  }, []);

  // Tick elapsed timer every second
  useEffect(() => {
    if (!activeSession) return;
    const timer = setInterval(() => {
      if (activeSession.started_at) {
        const start = new Date(activeSession.started_at).getTime();
        setElapsed(Math.floor((Date.now() - start) / 1000));
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [activeSession]);

  useEffect(() => {
    let cancelled = false;
    getDashboardTrends(trendDays)
      .then(r => { if (!cancelled) setTrends(r.items); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setTrendsLoading(false); });
    return () => { cancelled = true; };
  }, [trendDays]);

  // Focus timer from command palette
  useEffect(() => {
    if (searchParams.get('focus') === 'timer') {
      setTimeout(() => {
        document.getElementById('study-timer')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 300);
      setSearchParams({}, { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleToggle = async (id: number, completed: boolean) => {
    setUpdatingId(id);
    setToggleError('');
    try {
      await updatePlan(id, !completed);
      refresh();
    } catch (err) {
      setToggleError(getApiErrorMessage(err, '更新失败，请检查后端服务。'));
    } finally {
      setUpdatingId(null);
    }
  };

  const handleStartSession = async () => {
    setSessionLoading(true);
    setSessionError('');
    try {
      const s = await startSession({ subject: sessionSubject || undefined, note: sessionNote || undefined });
      setActiveSession(s);
      setElapsed(0);
    } catch (err) {
      setSessionError(getApiErrorMessage(err, '开始会话失败。'));
    } finally {
      setSessionLoading(false);
    }
  };

  const handleStopSession = async () => {
    if (!activeSession) return;
    setSessionLoading(true);
    setSessionError('');
    try {
      await stopSession(activeSession.id);
      setActiveSession(null);
      setElapsed(0);
      setSessionSubject('');
      setSessionNote('');
      refresh();
    } catch (err) {
      setSessionError(getApiErrorMessage(err, '结束会话失败。'));
    } finally {
      setSessionLoading(false);
    }
  };

  const formatElapsed = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}` : `${m}:${String(sec).padStart(2, '0')}`;
  };

  useReviewTitle(stats?.today_review_errors ?? 0);

  if (!stats) return <div className="p-6 text-gray-400">加载中...</div>;

  const reviewCount = stats.today_review_errors;

  const cards = [
    { label: '今日任务', value: `${stats.today_completed}/${stats.today_tasks}`, color: 'bg-blue-500', to: '/plan' as const },
    { label: '连续打卡', value: `${stats.streak_days} 天`, color: 'bg-green-500', to: null },
    { label: '今日复习', value: `${reviewCount} 题`, color: 'bg-orange-500', to: '/errors?filter=review' as const },
    { label: '今日学习', value: `${stats.today_study_minutes} 分钟`, color: 'bg-indigo-500', to: null },
    { label: '未掌握错题', value: stats.unmastered_errors, color: 'bg-red-500', to: '/errors' as const },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 dark:text-gray-100">学习工作台</h1>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {cards.map(c => {
          const card = (
            <div className={`bg-white dark:bg-gray-800 rounded-xl shadow p-5 ${c.to ? 'cursor-pointer hover:shadow-md transition-shadow' : ''}`}>
              <div className={`w-10 h-10 ${c.color} rounded-lg flex items-center justify-center text-white text-lg mb-3`}>
                {c.label[0]}
              </div>
              <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">{c.value}</div>
              <div className="text-sm text-gray-500 dark:text-gray-400">{c.label}</div>
            </div>
          );
          return c.to ? <Link key={c.label} to={c.to} className="block">{card}</Link> : <div key={c.label}>{card}</div>;
        })}
      </div>
      {/* Study timer */}
      <div id="study-timer" className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 mb-4">
        <h2 className="text-lg font-semibold mb-3">专注计时</h2>
        {sessionError && <div className="mb-2 p-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded text-sm text-red-700 dark:text-red-300">{sessionError}</div>}
        {activeSession ? (
          <div className="flex items-center gap-4">
            <div className="text-3xl font-mono font-bold text-indigo-600">{formatElapsed(elapsed)}</div>
            <div className="flex-1 min-w-0">
              {activeSession.subject && <span className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs mr-2">{activeSession.subject}</span>}
              {activeSession.note && <span className="text-xs text-gray-400 truncate">{activeSession.note}</span>}
            </div>
            <button onClick={handleStopSession} disabled={sessionLoading} className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 text-sm">
              {sessionLoading ? '结束中...' : '结束'}
            </button>
          </div>
        ) : (
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <input className="w-full border rounded-lg px-3 py-2 text-sm mb-2 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="科目（可选）" value={sessionSubject} onChange={e => setSessionSubject(e.target.value)} />
              <input className="w-full border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="备注（可选）" value={sessionNote} onChange={e => setSessionNote(e.target.value)} />
            </div>
            <button onClick={handleStartSession} disabled={sessionLoading} className="px-5 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm whitespace-nowrap">
              {sessionLoading ? '启动中...' : '开始学习'}
            </button>
          </div>
        )}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
        <h2 className="text-lg font-semibold mb-4">今日计划</h2>
        {toggleError && (
          <div className="mb-3 p-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
            {toggleError}
          </div>
        )}
        {todayPlans.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无今日计划，去「学习计划」页面生成吧</p>
        ) : (
          <ul className="space-y-2">
            {todayPlans.map((p) => (
              <li
                key={p.id}
                className={`flex items-center gap-3 text-sm cursor-pointer select-none ${updatingId === p.id ? 'opacity-50' : ''}`}
                onClick={() => updatingId !== p.id && handleToggle(p.id, p.completed)}
              >
                <span className={p.completed ? 'text-green-500' : 'text-gray-300'}>
                  {p.completed ? '✓' : '○'}
                </span>
                <span className="text-gray-500">{p.subject}</span>
                <span className={p.completed ? 'line-through text-gray-400' : 'text-gray-700'}>
                  {p.task}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4 bg-white dark:bg-gray-800 rounded-xl shadow p-5">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600 dark:text-gray-300">
            {reviewCount > 0
              ? `今天有 ${reviewCount} 道错题待复习`
              : '今天暂无需要复习的错题'}
          </span>
          {reviewCount > 0 && (
            <Link to="/errors?filter=review" className="text-sm text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300">
              去复习 →
            </Link>
          )}
        </div>
      </div>

      {/* Trends */}
      <div className="mt-4 bg-white dark:bg-gray-800 rounded-xl shadow p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold dark:text-gray-100">学习趋势</h2>
          <div className="flex gap-1">
            {([7, 30] as const).map(d => (
              <button
                key={d}
                onClick={() => { setTrendsLoading(true); setTrendDays(d); }}
                className={`px-2 py-1 rounded text-xs ${trendDays === d ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'}`}
              >
                {d} 天
              </button>
            ))}
          </div>
        </div>

        {trendsLoading ? (
          <p className="text-gray-400 text-sm">加载中...</p>
        ) : trends.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无数据</p>
        ) : (() => {
          const maxPlans = Math.max(...trends.map(x => x.plans_total), 1);
          const maxExam = Math.max(...trends.map(x => x.exam_attempts), 1);
          const maxStudy = Math.max(...trends.map(x => x.study_minutes), 1);
          const maxErrors = Math.max(...trends.map(x => x.errors_created + x.errors_review_due), 1);
          return (
          <div className="space-y-4">
            {/* Plans chart */}
            <div>
              <div className="text-xs text-gray-500 mb-1.5">计划完成</div>
              <div className="flex items-end gap-1" style={{ height: 60 }}>
                {trends.map(t => {
                  const h = t.plans_total > 0 ? (t.plans_total / maxPlans) * 100 : 0;
                  const doneH = t.plans_total > 0 ? (t.plans_completed / t.plans_total) * 100 : 0;
                  return (
                    <div key={t.date} className="flex-1 flex flex-col items-center" title={`${t.date}: ${t.plans_completed}/${t.plans_total}`}>
                      <div className="w-full flex flex-col justify-end" style={{ height: 50 }}>
                        <div className="w-full rounded-t" style={{ height: `${h}%`, background: '#e5e7eb' }}>
                          <div className="w-full rounded-t" style={{ height: `${doneH}%`, background: '#3b82f6' }} />
                        </div>
                      </div>
                      <div className="text-[9px] text-gray-400 mt-0.5">{t.date.slice(5)}</div>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-3 mt-1 text-[10px] text-gray-400">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-500 rounded-sm inline-block" />已完成</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-gray-200 rounded-sm inline-block" />未完成</span>
              </div>
            </div>

            {/* Exam chart */}
            <div>
              <div className="text-xs text-gray-500 mb-1.5">真题练习</div>
              <div className="flex items-end gap-1" style={{ height: 60 }}>
                {trends.map(t => {
                  const h = t.exam_attempts > 0 ? (t.exam_attempts / maxExam) * 100 : 0;
                  const correctH = t.exam_attempts > 0 ? (t.exam_correct / t.exam_attempts) * 100 : 0;
                  return (
                    <div key={t.date} className="flex-1 flex flex-col items-center" title={`${t.date}: ${t.exam_correct}/${t.exam_attempts}`}>
                      <div className="w-full flex flex-col justify-end" style={{ height: 50 }}>
                        <div className="w-full rounded-t" style={{ height: `${h}%`, background: '#e5e7eb' }}>
                          <div className="w-full rounded-t" style={{ height: `${correctH}%`, background: '#10b981' }} />
                        </div>
                      </div>
                      <div className="text-[9px] text-gray-400 mt-0.5">{t.date.slice(5)}</div>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-3 mt-1 text-[10px] text-gray-400">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-500 rounded-sm inline-block" />正确</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-gray-200 rounded-sm inline-block" />总计</span>
              </div>
            </div>

            {/* Study minutes chart */}
            <div>
              <div className="text-xs text-gray-500 mb-1.5">学习时长（分钟）</div>
              <div className="flex items-end gap-1" style={{ height: 60 }}>
                {trends.map(t => {
                  const h = t.study_minutes > 0 ? (t.study_minutes / maxStudy) * 100 : 0;
                  return (
                    <div key={t.date} className="flex-1 flex flex-col items-center" title={`${t.date}: ${t.study_minutes} 分钟`}>
                      <div className="w-full flex flex-col justify-end" style={{ height: 50 }}>
                        <div className="w-full rounded-t" style={{ height: `${h}%`, background: '#6366f1' }} />
                      </div>
                      <div className="text-[9px] text-gray-400 mt-0.5">{t.date.slice(5)}</div>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-3 mt-1 text-[10px] text-gray-400">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-indigo-500 rounded-sm inline-block" />学习分钟</span>
              </div>
            </div>

            {/* Errors chart */}
            <div>
              <div className="text-xs text-gray-500 mb-1.5">错题动态</div>
              <div className="flex items-end gap-1" style={{ height: 60 }}>
                {trends.map(t => {
                  const createdH = t.errors_created > 0 ? (t.errors_created / maxErrors) * 100 : 0;
                  const dueH = t.errors_review_due > 0 ? (t.errors_review_due / maxErrors) * 100 : 0;
                  return (
                    <div key={t.date} className="flex-1 flex flex-col items-center" title={`${t.date}: 新增${t.errors_created}, 待复习${t.errors_review_due}`}>
                      <div className="w-full flex flex-col justify-end" style={{ height: 50 }}>
                        <div style={{ height: `${dueH}%`, background: '#f97316' }} />
                        <div style={{ height: `${createdH}%`, background: '#ef4444' }} />
                      </div>
                      <div className="text-[9px] text-gray-400 mt-0.5">{t.date.slice(5)}</div>
                    </div>
                  );
                })}
              </div>
              <div className="flex gap-3 mt-1 text-[10px] text-gray-400">
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-sm inline-block" />新增</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 bg-orange-500 rounded-sm inline-block" />待复习</span>
              </div>
            </div>
          </div>
          );
        })()}
      </div>
    </div>
  );
}
