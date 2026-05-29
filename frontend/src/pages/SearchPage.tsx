import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { globalSearch, getApiErrorMessage } from '../api/client';
import type { SearchResult } from '../api/client';

const TYPE_CONFIG: Record<string, { label: string; color: string; path: string }> = {
  material: { label: '资料', color: 'bg-blue-100 text-blue-700', path: '/materials' },
  error: { label: '错题', color: 'bg-red-100 text-red-700', path: '/errors' },
  plan: { label: '计划', color: 'bg-green-100 text-green-700', path: '/plan' },
  exam: { label: '真题', color: 'bg-purple-100 text-purple-700', path: '/exam' },
  chat: { label: '问答', color: 'bg-yellow-100 text-yellow-700', path: '/qa' },
  problem: { label: '解析', color: 'bg-orange-100 text-orange-700', path: '/problems' },
};

const ALL_TYPES = ['materials', 'errors', 'plans', 'exam', 'chat', 'problems'];
const TYPE_LABELS: Record<string, string> = {
  materials: '资料', errors: '错题', plans: '计划',
  exam: '真题', chat: '问答', problems: '解析',
};

const HISTORY_KEY = 'math_agent_search_history';
const MAX_HISTORY = 5;

function loadHistory(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveToHistory(query: string) {
  const history = loadHistory().filter(h => h !== query);
  history.unshift(query);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);
  const [history, setHistory] = useState<string[]>(loadHistory);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doSearch = useCallback(async (q: string, types: Set<string>) => {
    if (!q.trim()) return;
    setLoading(true);
    setError('');
    setSearched(true);
    try {
      const t = types.size > 0 ? [...types].join(',') : undefined;
      const resp = await globalSearch(q.trim(), t);
      setResults(resp.results);
      saveToHistory(q.trim());
      setHistory(loadHistory());
    } catch (err) {
      setError(getApiErrorMessage(err, '搜索失败，请检查后端服务。'));
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = () => {
    doSearch(query, activeTypes);
    setShowSuggestions(false);
  };

  // 输入防抖（300ms）
  const handleInputChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value.trim()) {
      debounceRef.current = setTimeout(() => {
        doSearch(value, activeTypes);
      }, 300);
    } else {
      setResults([]);
      setSearched(false);
    }
  };

  const handleSelectHistory = (h: string) => {
    setQuery(h);
    setShowSuggestions(false);
    doSearch(h, activeTypes);
  };

  const handleClearHistory = () => {
    localStorage.removeItem(HISTORY_KEY);
    setHistory([]);
  };

  // 点击外部关闭建议
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (inputRef.current && !inputRef.current.parentElement?.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const toggleType = (t: string) => {
    setActiveTypes(prev => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const handleClick = (r: SearchResult) => {
    const cfg = TYPE_CONFIG[r.type];
    if (cfg?.path) navigate(`${cfg.path}?open=${r.id}`);
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 dark:text-gray-100">全局搜索</h1>

      <div className="flex gap-2 mb-3 relative">
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
            placeholder="搜索资料、错题、计划、真题、问答、解析..."
            value={query}
            onChange={e => handleInputChange(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            onFocus={() => { if (history.length > 0 && !query) setShowSuggestions(true); }}
          />
          {/* 搜索历史建议 */}
          {showSuggestions && history.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white dark:bg-gray-800 border dark:border-gray-600 rounded-lg shadow-lg z-10">
              <div className="flex items-center justify-between px-3 py-1.5 border-b dark:border-gray-700">
                <span className="text-xs text-gray-400">最近搜索</span>
                <button onClick={handleClearHistory} className="text-xs text-gray-400 hover:text-red-500">清空</button>
              </div>
              {history.map(h => (
                <button
                  key={h}
                  onClick={() => handleSelectHistory(h)}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-200"
                >{h}</button>
              ))}
            </div>
          )}
        </div>
        <button
          onClick={handleSearch}
          disabled={loading || !query.trim()}
          className="px-5 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {loading ? '搜索中...' : '搜索'}
        </button>
      </div>

      <div className="flex gap-1.5 mb-4 flex-wrap">
        {ALL_TYPES.map(t => (
          <button
            key={t}
            onClick={() => toggleType(t)}
            className={`px-2.5 py-1 rounded text-xs ${
              activeTypes.has(t) ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {TYPE_LABELS[t]}
          </button>
        ))}
        {activeTypes.size > 0 && (
          <button onClick={() => setActiveTypes(new Set())} className="px-2 py-1 text-xs text-gray-400 hover:text-gray-600">
            清除筛选
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">{error}</div>
      )}

      {loading ? (
        <p className="text-gray-400 text-sm">搜索中...</p>
      ) : searched && results.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-10 text-center">
          <p className="text-gray-400 text-sm">未找到匹配结果</p>
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-2">
          {results.map((r, i) => {
            const cfg = TYPE_CONFIG[r.type] || { label: r.type, color: 'bg-gray-100 text-gray-600', path: '' };
            return (
              <div
                key={`${r.type}-${r.id}-${i}`}
                className={`bg-white dark:bg-gray-800 rounded-xl shadow p-4 ${cfg.path ? 'cursor-pointer hover:shadow-md' : ''}`}
                onClick={() => handleClick(r)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`px-2 py-0.5 rounded text-xs ${cfg.color}`}>{cfg.label}</span>
                  <span className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{r.title || '（无标题）'}</span>
                  {r.created_at && <span className="text-xs text-gray-400 ml-auto">{r.created_at.slice(0, 10)}</span>}
                </div>
                <p className="text-xs text-gray-500 line-clamp-2">{r.snippet}</p>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
