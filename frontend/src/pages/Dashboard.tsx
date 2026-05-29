import { useEffect, useState, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Treemap, ResponsiveContainer } from 'recharts';
import MiniBarChart from '../components/MiniBarChart';
import { getDashboard, getDashboardTrends, getErrorStats, listPlans, updatePlan, getActiveSession, startSession, stopSession, getApiErrorMessage } from '../api/client';
import type { DashboardStats, StudyPlanItem, TrendDay, StudySessionItem, ErrorStats } from '../api/client';
import { formatLocalDate } from '../utils/date';
import { useReviewTitle } from '../hooks/useDocumentTitle';
import { requestNotificationPermission, sendReviewNotification } from '../utils/pwa';

const TREEMAP_COLORS = ['#3b82f6', '#ef4444', '#f59e0b', '#10b981', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'];

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

  // Error stats for knowledge point analysis
  const [errorStats, setErrorStats] = useState<ErrorStats | null>(null);

  const today = formatLocalDate();

  const refresh = useCallback(() => {
    getDashboard().then(setStats).catch(() => {});
    listPlans(today).then(setTodayPlans).catch(() => {});
    getErrorStats().then(setErrorStats).catch(() => {});
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

  // 有待复习错题时请求通知权限并发送提醒（每次会话只通知一次）
  useEffect(() => {
    const due = stats?.today_review_errors ?? 0;
    if (due > 0 && 'Notification' in window && Notification.permission === 'default') {
      requestNotificationPermission();
    }
    if (due > 0 && Notification.permission === 'granted' && !sessionStorage.getItem('review_notified')) {
      sendReviewNotification(due);
      sessionStorage.setItem('review_notified', '1');
    }
  }, [stats?.today_review_errors]);

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
          const dates = trends.map(t => t.date);
          const maxPlans = Math.max(...trends.map(x => x.plans_total), 1);
          const maxExam = Math.max(...trends.map(x => x.exam_attempts), 1);
          const maxStudy = Math.max(...trends.map(x => x.study_minutes), 1);
          const maxErrors = Math.max(...trends.map(x => x.errors_created + x.errors_review_due), 1);
          return (
          <div className="space-y-4">
            <div>
              <div className="text-xs text-gray-500 mb-1.5">计划完成</div>
              <MiniBarChart
                dates={dates}
                max={maxPlans}
                bars={trends.map(t => [
                  { value: t.plans_total, color: '#e5e7eb' },
                  { value: t.plans_completed, color: '#3b82f6' },
                ])}
                tooltips={trends.map(t => `${t.date}: ${t.plans_completed}/${t.plans_total}`)}
                legends={[{ label: '已完成', color: '#3b82f6' }, { label: '未完成', color: '#e5e7eb' }]}
              />
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1.5">真题练习</div>
              <MiniBarChart
                dates={dates}
                max={maxExam}
                bars={trends.map(t => [
                  { value: t.exam_attempts, color: '#e5e7eb' },
                  { value: t.exam_correct, color: '#10b981' },
                ])}
                tooltips={trends.map(t => `${t.date}: ${t.exam_correct}/${t.exam_attempts}`)}
                legends={[{ label: '正确', color: '#10b981' }, { label: '总计', color: '#e5e7eb' }]}
              />
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1.5">学习时长（分钟）</div>
              <MiniBarChart
                dates={dates}
                max={maxStudy}
                bars={trends.map(t => [{ value: t.study_minutes, color: '#6366f1' }])}
                tooltips={trends.map(t => `${t.date}: ${t.study_minutes} 分钟`)}
                legends={[{ label: '学习分钟', color: '#6366f1' }]}
              />
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1.5">错题动态</div>
              <MiniBarChart
                dates={dates}
                max={maxErrors}
                bars={trends.map(t => [
                  { value: t.errors_created, color: '#ef4444' },
                  { value: t.errors_review_due, color: '#f97316' },
                ])}
                tooltips={trends.map(t => `${t.date}: 新增${t.errors_created}, 待复习${t.errors_review_due}`)}
                legends={[{ label: '新增', color: '#ef4444' }, { label: '待复习', color: '#f97316' }]}
              />
            </div>
          </div>
          );
        })()}
      </div>

      {/* 知识点掌握热力图 + 薄弱环节分析 */}
      {errorStats && errorStats.by_knowledge_point.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
          {/* 知识点 Treemap */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
            <h2 className="text-lg font-semibold mb-3 dark:text-gray-100">知识点错题分布</h2>
            <ResponsiveContainer width="100%" height={200}>
              <Treemap
                data={errorStats.by_knowledge_point}
                dataKey="count"
                nameKey="name"
                stroke="none"
                content={({ x, y, width, height, name, index }: { x: number; y: number; width: number; height: number; name: string; index: number }) => {
                  if (width < 30 || height < 20) return <g />;
                  return (
                    <g>
                      <rect x={x} y={y} width={width} height={height} fill={TREEMAP_COLORS[index % TREEMAP_COLORS.length]} rx={4} />
                      {width > 50 && height > 30 && (
                        <text x={x + width / 2} y={y + height / 2} textAnchor="middle" dominantBaseline="middle" fill="#fff" fontSize={width > 80 ? 12 : 10}>
                          {name.length > 6 ? name.slice(0, 6) + '…' : name}
                        </text>
                      )}
                    </g>
                  );
                }}
              />
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-2 mt-2">
              {errorStats.by_knowledge_point.slice(0, 6).map((kp, i) => (
                <span key={kp.name} className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
                  <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: TREEMAP_COLORS[i % TREEMAP_COLORS.length] }} />
                  {kp.name} ({kp.count})
                </span>
              ))}
            </div>
          </div>

          {/* 薄弱环节分析 */}
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5">
            <h2 className="text-lg font-semibold mb-3 dark:text-gray-100">薄弱环节分析</h2>
            <p className="text-xs text-gray-400 mb-3">根据错题数量自动识别需要重点复习的知识点</p>
            <div className="space-y-3">
              {errorStats.by_knowledge_point.slice(0, 3).map((kp, i) => {
                const total = errorStats.total || 1;
                const pct = Math.round((kp.count / total) * 100);
                const severity = i === 0 ? 'text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400' :
                  i === 1 ? 'text-orange-600 bg-orange-50 dark:bg-orange-900/20 dark:text-orange-400' :
                  'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20 dark:text-yellow-400';
                const barColor = i === 0 ? 'bg-red-500' : i === 1 ? 'bg-orange-500' : 'bg-yellow-500';
                return (
                  <div key={kp.name} className={`rounded-lg p-3 ${severity}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium">#{i + 1} {kp.name}</span>
                      <span className="text-xs">{kp.count} 道错题 · 占比 {pct}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-black/10 rounded-full overflow-hidden">
                      <div className={`h-full ${barColor} rounded-full`} style={{ width: `${Math.min(pct * 2, 100)}%` }} />
                    </div>
                    <p className="text-xs mt-1.5 opacity-75">
                      {i === 0 ? '最高优先级：建议每天复习此知识点，重做错题并总结规律' :
                       i === 1 ? '次高优先级：建议本周安排专项练习，巩固薄弱环节' :
                       '需关注：建议结合资料库中的相关内容进行查漏补缺'}
                    </p>
                  </div>
                );
              })}
            </div>
            {errorStats.by_knowledge_point.length > 3 && (
              <Link to="/errors" className="block mt-3 text-xs text-blue-500 hover:text-blue-700 text-center">
                查看全部 {errorStats.by_knowledge_point.length} 个知识点 →
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
