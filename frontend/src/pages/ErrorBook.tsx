import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { listErrors, createError, updateError, deleteError, getReviewSettings, updateReviewSettings, getErrorStats, getApiErrorMessage } from '../api/client';
import type { ErrorBookItem, ErrorStats } from '../api/client';
import LatexRenderer from '../components/LatexRenderer';
import { formatLocalDate } from '../utils/date';

const emptyForm = {
  subject: '', chapter: '', knowledge_point: '', question: '',
  user_answer: '', correct_answer: '', error_type: '', error_reason: '',
  correct_approach: '', review_suggestion: '', tags: '', next_review_date: '',
};

const validFilters = ['all', 'unmastered', 'mastered', 'review'] as const;
type Filter = (typeof validFilters)[number];

function isValidFilter(v: string | null): v is Filter {
  return v !== null && validFilters.includes(v as Filter);
}

function getFilterFromSearchParams(sp: URLSearchParams): Filter {
  const v = sp.get('filter');
  return isValidFilter(v) ? v : 'all';
}

function fetchErrorsByFilter(filter: Filter): Promise<ErrorBookItem[]> {
  const mastered = filter === 'all' ? undefined : filter === 'mastered';
  if (filter === 'review') {
    const today = formatLocalDate();
    return listErrors(false).then(all =>
      all.filter((e: ErrorBookItem) => e.next_review_date && e.next_review_date <= today)
    );
  }
  return listErrors(mastered);
}

function BarRow({ label, count, max, color }: { label: string; count: number; max: number; color: string }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="w-24 truncate text-gray-600 dark:text-gray-300 shrink-0" title={label}>{label}</span>
      <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
        <div className={`h-full ${color} rounded`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right text-gray-500 dark:text-gray-400 text-xs">{count}</span>
    </div>
  );
}

function ErrorStatsPanel({ stats }: { stats: ErrorStats }) {
  const maxSubject = Math.max(1, ...stats.by_subject.map(s => s.count));
  const maxType = Math.max(1, ...stats.by_error_type.map(s => s.count));
  const maxKp = Math.max(1, ...stats.by_knowledge_point.map(s => s.count));
  const maxTrend = Math.max(1, ...stats.created_last_30_days.map(d => d.count));

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: '总错题', value: stats.total, color: 'text-gray-800 dark:text-gray-100' },
          { label: '已掌握', value: stats.mastered, color: 'text-green-600' },
          { label: '未掌握', value: stats.unmastered, color: 'text-orange-500' },
          { label: '今日待复习', value: stats.due_today, color: 'text-red-500' },
        ].map(c => (
          <div key={c.label} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 text-center">
            <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{c.label}</div>
          </div>
        ))}
      </div>

      {/* Distributions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* By subject */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">科目分布</h4>
          {stats.by_subject.length === 0 ? (
            <p className="text-xs text-gray-400">暂无数据</p>
          ) : (
            <div className="space-y-1.5">
              {stats.by_subject.map(s => (
                <BarRow key={s.name} label={s.name} count={s.count} max={maxSubject} color="bg-blue-500" />
              ))}
            </div>
          )}
        </div>

        {/* By error type */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">错误类型</h4>
          {stats.by_error_type.length === 0 ? (
            <p className="text-xs text-gray-400">暂无数据</p>
          ) : (
            <div className="space-y-1.5">
              {stats.by_error_type.map(s => (
                <BarRow key={s.name} label={s.name} count={s.count} max={maxType} color="bg-red-400" />
              ))}
            </div>
          )}
        </div>

        {/* By knowledge point */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">知识点 Top 10</h4>
          {stats.by_knowledge_point.length === 0 ? (
            <p className="text-xs text-gray-400">暂无数据</p>
          ) : (
            <div className="space-y-1.5">
              {stats.by_knowledge_point.map(s => (
                <BarRow key={s.name} label={s.name} count={s.count} max={maxKp} color="bg-purple-400" />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 30-day trend */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">最近 30 天新增错题</h4>
        <div className="flex items-end gap-px h-20">
          {stats.created_last_30_days.map(d => {
            const h = maxTrend > 0 ? Math.max(1, Math.round((d.count / maxTrend) * 100)) : 1;
            return (
              <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full group">
                <div
                  className="w-full bg-teal-400 dark:bg-teal-500 rounded-t"
                  style={{ height: `${h}%` }}
                  title={`${d.date}: ${d.count}`}
                />
              </div>
            );
          })}
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-1">
          <span>{stats.created_last_30_days[0]?.date.slice(5)}</span>
          <span>{stats.created_last_30_days[stats.created_last_30_days.length - 1]?.date.slice(5)}</span>
        </div>
      </div>
    </div>
  );
}

export default function ErrorBook() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filter = getFilterFromSearchParams(searchParams);
  const [errors, setErrors] = useState<ErrorBookItem[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);

  // Review settings
  const [showSettings, setShowSettings] = useState(false);
  const [intervalsStr, setIntervalsStr] = useState('1,3,7,14');
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState('');
  const [settingsError, setSettingsError] = useState('');
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [highlightId, setHighlightId] = useState<number | null>(null);
  const effectSeq = useRef(0);

  // Stats
  const [showStats, setShowStats] = useState(false);
  const [stats, setStats] = useState<ErrorStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError, setStatsError] = useState('');

  useEffect(() => {
    const seq = ++effectSeq.current;
    fetchErrorsByFilter(filter).then(items => {
      if (seq !== effectSeq.current) return;
      setError('');
      setErrors(items);
    }).catch(err => {
      if (seq !== effectSeq.current) return;
      setError(getApiErrorMessage(err, '加载错题失败，请检查后端服务。'));
    });
    return () => { effectSeq.current += 1; };
  }, [filter]);

  // Deep link: auto-expand and highlight
  useEffect(() => {
    const openId = searchParams.get('open');
    if (openId) {
      const id = parseInt(openId, 10);
      if (!isNaN(id)) {
        setTimeout(() => {
          setExpandedId(id);
          setHighlightId(id);
          setSearchParams({}, { replace: true });
          setTimeout(() => setHighlightId(null), 3000);
        }, 0);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadErrors = useCallback(async () => {
    try {
      const items = await fetchErrorsByFilter(filter);
      setError('');
      setErrors(items);
    } catch (err) {
      setError(getApiErrorMessage(err, '加载错题失败，请检查后端服务。'));
    }
  }, [filter]);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError('');
    try {
      const data = await getReviewSettings();
      setIntervalsStr(data.intervals.join(','));
    } catch (err) {
      setSettingsError(getApiErrorMessage(err, '加载复习策略失败。'));
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    setStatsError('');
    try {
      const data = await getErrorStats();
      setStats(data);
    } catch (err) {
      setStatsError(getApiErrorMessage(err, '加载统计数据失败。'));
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const handleSaveSettings = async () => {
    setSettingsMsg('');
    setSettingsError('');
    const nums = intervalsStr.split(',').map(s => parseInt(s.trim(), 10));
    if (nums.some(isNaN)) {
      setSettingsError('请输入有效的数字，用逗号分隔');
      return;
    }
    try {
      await updateReviewSettings(nums);
      setSettingsMsg('复习策略已保存');
    } catch (err) {
      setSettingsError(getApiErrorMessage(err, '保存复习策略失败。'));
    }
  };

  const handleAdd = async () => {
    if (!form.question.trim()) return;
    setError('');
    setAdding(true);
    try {
      await createError(form);
      setForm(emptyForm);
      setShowAdd(false);
      await loadErrors();
    } catch (err) {
      setError(getApiErrorMessage(err, '保存错题失败，请检查后端服务。'));
    } finally {
      setAdding(false);
    }
  };

  const toggleMastered = async (item: ErrorBookItem) => {
    if (updatingId === item.id || deletingId === item.id) return;
    setError('');
    setUpdatingId(item.id);
    try {
      await updateError(item.id, { mastered: !item.mastered });
      await loadErrors();
    } catch (err) {
      setError(getApiErrorMessage(err, '更新错题状态失败，请检查后端服务。'));
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (updatingId === id || deletingId === id) return;
    setError('');
    setDeletingId(id);
    try {
      await deleteError(id);
      await loadErrors();
    } catch (err) {
      setError(getApiErrorMessage(err, '删除错题失败，请检查后端服务。'));
    } finally {
      setDeletingId(null);
    }
  };

  const set = (key: string, val: string) => setForm(f => ({ ...f, [key]: val }));

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold dark:text-gray-100">错题本</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
        >
          {showAdd ? '取消' : '添加错题'}
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        {(['all', 'unmastered', 'mastered', 'review'] as const).map(f => (
          <button
            key={f}
            onClick={() => { setError(''); if (f === 'all') { setSearchParams({}); } else { setSearchParams({ filter: f }); } }}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              filter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {{ all: '全部', unmastered: '未掌握', mastered: '已掌握', review: '今日复习' }[f]}
          </button>
        ))}
      </div>

      {/* Stats toggle */}
      <div className="mb-4">
        <button
          onClick={() => {
            if (!showStats) loadStats();
            setShowStats(!showStats);
          }}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          {showStats ? '收起错题统计' : '错题统计分析'} ▸
        </button>
        {showStats && (
          <div className="mt-3">
            {statsLoading && <p className="text-sm text-gray-400">加载中...</p>}
            {statsError && <p className="text-sm text-red-500">{statsError}</p>}
            {stats && <ErrorStatsPanel stats={stats} />}
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Review settings */}
      <div className="mb-4">
        <button
          onClick={() => {
            if (!showSettings) loadSettings();
            setShowSettings(!showSettings);
          }}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          {showSettings ? '收起复习策略设置' : '复习策略设置'} ▸
        </button>
        {showSettings && (
          <div className="mt-2 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg flex items-center gap-3 flex-wrap">
            <span className="text-xs text-gray-500 dark:text-gray-400">掌握后复习间隔（天）：</span>
            <input
              className="border rounded px-2 py-1 text-sm w-48 dark:bg-gray-600 dark:border-gray-500 dark:text-gray-100"
              placeholder="1,3,7,14"
              value={intervalsStr}
              onChange={e => setIntervalsStr(e.target.value)}
              disabled={settingsLoading}
            />
            <button
              onClick={handleSaveSettings}
              disabled={settingsLoading}
              className="px-3 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 disabled:opacity-50"
            >
              保存
            </button>
            {settingsMsg && <span className="text-xs text-green-600">{settingsMsg}</span>}
            {settingsError && <span className="text-xs text-red-500">{settingsError}</span>}
          </div>
        )}
      </div>

      {showAdd && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 mb-6">
          <div className="grid grid-cols-3 gap-3 mb-3">
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="科目" value={form.subject} onChange={e => set('subject', e.target.value)} />
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="章节" value={form.chapter} onChange={e => set('chapter', e.target.value)} />
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="知识点" value={form.knowledge_point} onChange={e => set('knowledge_point', e.target.value)} />
          </div>
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="题目内容" value={form.question} onChange={e => set('question', e.target.value)} />
          <div className="grid grid-cols-2 gap-3 mb-3">
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="你的错误答案" value={form.user_answer} onChange={e => set('user_answer', e.target.value)} />
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="正确答案/解析" value={form.correct_answer} onChange={e => set('correct_answer', e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="错误类型（如计算错误）" value={form.error_type} onChange={e => set('error_type', e.target.value)} />
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="标签（逗号分隔）" value={form.tags} onChange={e => set('tags', e.target.value)} />
            <input type="date" className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" title="下次复习时间" value={form.next_review_date} onChange={e => set('next_review_date', e.target.value)} />
          </div>
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-16 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="错误原因" value={form.error_reason} onChange={e => set('error_reason', e.target.value)} />
          <div className="grid grid-cols-2 gap-3 mb-3">
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="正确思路" value={form.correct_approach} onChange={e => set('correct_approach', e.target.value)} />
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="复习建议" value={form.review_suggestion} onChange={e => set('review_suggestion', e.target.value)} />
          </div>
          <button onClick={handleAdd} disabled={adding} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm">{adding ? '保存中...' : '保存'}</button>
        </div>
      )}

      {errors.length === 0 ? (
        <p className="text-gray-400 text-sm">
          {filter === 'review' ? '今天暂无需要复习的错题' : '暂无错题'}
        </p>
      ) : (
        <div className="space-y-3">
          {errors.map(item => {
            const rowBusy = updatingId === item.id || deletingId === item.id;
            return (
            <div key={item.id} className={`bg-white dark:bg-gray-800 rounded-xl shadow p-5 ${rowBusy ? 'opacity-50' : ''} ${item.mastered && !rowBusy ? 'opacity-60' : ''} ${highlightId === item.id ? 'ring-2 ring-blue-400' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  {item.subject && <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{item.subject}</span>}
                  {item.chapter && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">{item.chapter}</span>}
                  {item.knowledge_point && <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">{item.knowledge_point}</span>}
                  {item.error_type && <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">{item.error_type}</span>}
                  {item.tags && item.tags.split(',').map(t => t.trim()).filter(Boolean).map(tag => (
                    <span key={tag} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-300 rounded text-xs">{tag}</span>
                  ))}
                  <span className="px-2 py-0.5 bg-teal-100 text-teal-700 rounded text-xs">复习 {item.review_count} 次</span>
                </div>
                <div className="flex items-center gap-2">
                  {item.next_review_date && <span className="text-xs text-gray-400">复习: {item.next_review_date}</span>}
                  <button onClick={() => toggleMastered(item)} disabled={rowBusy} className={`text-xs px-2 py-1 rounded ${item.mastered ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {item.mastered ? '已掌握' : '标记掌握'}
                  </button>
                  <button onClick={() => setExpandedId(expandedId === item.id ? null : item.id)} className="text-blue-400 hover:text-blue-600 text-xs">
                    {expandedId === item.id ? '收起' : '展开'}
                  </button>
                  <button onClick={() => handleDelete(item.id)} disabled={rowBusy} className="text-red-400 hover:text-red-600 disabled:opacity-50 text-xs">{deletingId === item.id ? '删除中...' : '删除'}</button>
                </div>
              </div>

              <div className="prose prose-sm max-w-none mb-2">
                <LatexRenderer content={item.question} />
              </div>

              {expandedId === item.id && (
                <div className="mt-3 pt-3 border-t space-y-2 text-sm">
                  {item.user_answer && <div><span className="font-medium text-red-600">错误答案：</span><div className="prose prose-sm max-w-none dark:text-gray-100"><LatexRenderer content={item.user_answer} /></div></div>}
                  {item.correct_answer && <div><span className="font-medium text-green-600">正确答案：</span><div className="prose prose-sm max-w-none dark:text-gray-100"><LatexRenderer content={item.correct_answer} /></div></div>}
                  {item.error_reason && <div><span className="font-medium text-gray-600">错误原因：</span>{item.error_reason}</div>}
                  {item.correct_approach && <div><span className="font-medium text-blue-600">正确思路：</span>{item.correct_approach}</div>}
                  {item.review_suggestion && <div><span className="font-medium text-purple-600">复习建议：</span>{item.review_suggestion}</div>}
                </div>
              )}
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
