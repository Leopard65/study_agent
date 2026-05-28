import { useState } from 'react';
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

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError('');
    setSearched(true);
    try {
      const types = activeTypes.size > 0 ? [...activeTypes].join(',') : undefined;
      const resp = await globalSearch(query.trim(), types);
      setResults(resp.results);
    } catch (err) {
      setError(getApiErrorMessage(err, '搜索失败，请检查后端服务。'));
    } finally {
      setLoading(false);
    }
  };

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

      <div className="flex gap-2 mb-3">
        <input
          className="flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
          placeholder="搜索资料、错题、计划、真题、问答、解析..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
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
