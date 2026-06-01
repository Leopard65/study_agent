import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { uploadMaterial, listMaterials, searchMaterials, deleteMaterial, getMaterial, bulkDeleteMaterials, exportSelectedMaterials, retryMaterial, listParseJobs, cancelParseJob, getApiErrorMessage } from '../api/client';
import type { MaterialItem, MaterialDetail, MaterialSearchResult, ParseJobItem } from '../api/client';
import FileUpload from '../components/FileUpload';
import MaterialDetailModal from '../components/MaterialDetailModal';
import { useSafeAsync } from '../hooks/useSafeAsync';
import { useDeepLink } from '../hooks/useDeepLink';
import { downloadBlob } from '../utils/constants';

function HighlightedSnippet({ text }: { text: string }): ReactNode {
  const parts: ReactNode[] = [];
  let remaining = text;
  let key = 0;
  while (remaining.length > 0) {
    const start = remaining.indexOf('>>>');
    if (start === -1) {
      parts.push(remaining);
      break;
    }
    if (start > 0) parts.push(remaining.slice(0, start));
    const afterOpen = remaining.slice(start + 3);
    const end = afterOpen.indexOf('<<<');
    if (end === -1) {
      parts.push(remaining.slice(start));
      break;
    }
    parts.push(<mark key={key++}>{afterOpen.slice(0, end)}</mark>);
    remaining = afterOpen.slice(end + 3);
  }
  return <>{parts}</>;
}

const PAGE_SIZE = 20;

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: '等待解析', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' },
  processing: { label: '解析中', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
  ready: { label: '就绪', color: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
  failed: { label: '解析失败', color: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' },
};

function fetchFirstMaterials(): Promise<MaterialItem[]> {
  return listMaterials(PAGE_SIZE, 0);
}

export default function Materials() {
  const { run, cancel } = useSafeAsync();
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MaterialSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [loadingMaterials, setLoadingMaterials] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState<MaterialDetail | null>(null);
  const [detailLoadingId, setDetailLoadingId] = useState<number | null>(null);
  const [detailError, setDetailError] = useState('');
  const [detailInitialQuery, setDetailInitialQuery] = useState('');

  // Bulk operations
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [exportingSelected, setExportingSelected] = useState(false);

  // Retry
  const [retryingId, setRetryingId] = useState<number | null>(null);

  // Parse jobs
  const [parseJobs, setParseJobs] = useState<ParseJobItem[]>([]);
  const [showJobs, setShowJobs] = useState(false);
  const [cancellingJobId, setCancellingJobId] = useState<number | null>(null);

  // Polling for pending/processing materials and parse jobs
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refreshJobs = useCallback(async () => {
    try {
      const jobs = await listParseJobs({ limit: 30 });
      setParseJobs(jobs);
      return jobs;
    } catch { return []; }
  }, []);

  const startPolling = useCallback(() => {
    refreshJobs();
    if (!jobPollRef.current) {
      jobPollRef.current = setInterval(async () => {
        try {
          const jobs = await listParseJobs({ limit: 30 });
          setParseJobs(jobs);
          const hasActiveJob = jobs.some(j => j.status === 'pending' || j.status === 'processing');
          if (!hasActiveJob && jobPollRef.current) {
            clearInterval(jobPollRef.current);
            jobPollRef.current = null;
          }
        } catch { /* ignore */ }
      }, 2000);
    }
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const items = await listMaterials(100, 0);
        setMaterials(prev => {
          const map = new Map(items.map(m => [m.id, m]));
          return prev.map(m => map.get(m.id) || m);
        });
        const hasActive = items.some(m => m.status === 'pending' || m.status === 'processing');
        if (!hasActive && pollRef.current) {
          clearInterval(pollRef.current);
          pollRef.current = null;
        }
      } catch { /* ignore poll errors */ }
    }, 2000);
  }, [refreshJobs]);
  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (jobPollRef.current) {
      clearInterval(jobPollRef.current);
      jobPollRef.current = null;
    }
  }, []);
  useEffect(() => stopPolling, [stopPolling]);

  const jobsLoadedRef = useRef(false);
  useEffect(() => {
    run(() => fetchFirstMaterials()).then(items => {
      if (items !== undefined) {
        setMaterials(items);
        setHasMore(items.length === PAGE_SIZE);
      }
    }).catch(err => {
      setError(getApiErrorMessage(err, '加载资料失败，请检查后端服务。'));
    }).finally(() => {
      setLoadingMaterials(false);
    });
    // 加载初始解析任务列表（仅一次）
    if (!jobsLoadedRef.current) {
      jobsLoadedRef.current = true;
      listParseJobs({ limit: 30 }).then(jobs => {
        setParseJobs(jobs);
        const hasActive = jobs.some(j => j.status === 'pending' || j.status === 'processing');
        if (hasActive) startPolling();
      }).catch(() => {});
    }
    return cancel;
  }, [run, cancel, startPolling]);

  const loadFirstPage = useCallback(async () => {
    setLoadingMaterials(true);
    setError('');
    try {
      const items = await fetchFirstMaterials();
      setMaterials(items);
      setHasMore(items.length === PAGE_SIZE);
    } catch (err) {
      setError(getApiErrorMessage(err, '加载资料失败，请检查后端服务。'));
    } finally {
      setLoadingMaterials(false);
    }
  }, []);

  const handleLoadMore = async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    setError('');
    try {
      const items = await listMaterials(PAGE_SIZE, materials.length);
      setMaterials(prev => [...prev, ...items]);
      setHasMore(items.length === PAGE_SIZE);
    } catch (err) {
      setError(getApiErrorMessage(err, '加载资料失败，请检查后端服务。'));
    } finally {
      setLoadingMore(false);
    }
  };

  const handleUpload = async (file: File) => {
    setError('');
    try {
      await uploadMaterial(file);
    } catch (err) {
      setError(getApiErrorMessage(err, '上传失败，请检查文件或后端服务。'));
      return;
    }
    await loadFirstPage();
    startPolling();
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setError('');
    setSearching(true);
    setHasSearched(true);
    try {
      const r = await searchMaterials(query);
      setResults(r);
    } catch (err) {
      setResults([]);
      setError(getApiErrorMessage(err, '搜索失败，请检查后端服务。'));
    } finally {
      setSearching(false);
    }
  };

  const handleClearSearch = () => {
    setQuery('');
    setResults([]);
    setError('');
    setHasSearched(false);
  };

  const handleViewDetail = async (id: number, initialQuery?: string) => {
    setDetailError('');
    setDetailLoadingId(id);
    setDetailInitialQuery(initialQuery || '');
    try {
      const detail = await getMaterial(id);
      setSelectedMaterial(detail);
    } catch (err) {
      setDetailError(getApiErrorMessage(err, '加载资料详情失败，请检查后端服务。'));
    } finally {
      setDetailLoadingId(null);
    }
  };

  // Deep link: auto-open material detail (supports ?open=id&q=query)
  useDeepLink((id, q) => handleViewDetail(id, q).catch(() => {}));

  const handleDelete = async (id: number) => {
    if (deletingId === id) return;
    setError('');
    setDeletingId(id);
    try {
      await deleteMaterial(id);
      setMaterials(prev => prev.filter(m => m.id !== id));
      setResults(prev => prev.filter(r => r.material_id !== id));
      if (selectedMaterial?.id === id) setSelectedMaterial(null);
    } catch (err) {
      setError(getApiErrorMessage(err, '删除失败，请检查后端服务。'));
    } finally {
      setDeletingId(null);
    }
  };

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === materials.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(materials.map(m => m.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!window.confirm(`确认删除选中的 ${selectedIds.size} 个资料？此操作不可撤销。`)) return;
    const idsToDelete = Array.from(selectedIds);
    setBulkDeleting(true);
    setError('');
    try {
      const result = await bulkDeleteMaterials(idsToDelete);
      setSelectedIds(new Set());
      setSelectMode(false);
      await loadFirstPage();
      const deleteSet = new Set(idsToDelete);
      setResults(prev => prev.filter(r => !deleteSet.has(r.material_id)));
      if (selectedMaterial && deleteSet.has(selectedMaterial.id)) setSelectedMaterial(null);
      if (result.missing > 0) {
        setError(`已删除 ${result.deleted} 个，${result.missing} 个未找到。`);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, '批量删除失败，请检查后端服务。'));
    } finally {
      setBulkDeleting(false);
    }
  };

  const handleExportSelected = async () => {
    if (selectedIds.size === 0) return;
    setExportingSelected(true);
    setError('');
    try {
      const data = await exportSelectedMaterials(Array.from(selectedIds), true);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      downloadBlob(blob, `math_agent_materials_${new Date().toISOString().slice(0, 10)}.json`);
    } catch (err) {
      setError(getApiErrorMessage(err, '导出失败，请检查后端服务。'));
    } finally {
      setExportingSelected(false);
    }
  };

  const handleRetry = async (id: number) => {
    if (retryingId === id) return;
    setError('');
    setRetryingId(id);
    try {
      const updated = await retryMaterial(id);
      setMaterials(prev => prev.map(m => m.id === id ? { ...m, ...updated } : m));
      await refreshJobs();
      startPolling();
    } catch (err) {
      setError(getApiErrorMessage(err, '重试失败，请检查后端服务。'));
    } finally {
      setRetryingId(null);
    }
  };

  const handleCancelJob = async (jobId: number) => {
    if (cancellingJobId === jobId) return;
    setError('');
    setCancellingJobId(jobId);
    try {
      await cancelParseJob(jobId);
      await refreshJobs();
      // 同步更新 materials 列表中对应 material 的状态
      const job = parseJobs.find(j => j.id === jobId);
      if (job) {
        setMaterials(prev => prev.map(m =>
          m.id === job.material_id ? { ...m, status: 'failed', error_message: '任务已取消' } : m
        ));
      }
    } catch (err) {
      setError(getApiErrorMessage(err, '取消任务失败。'));
    } finally {
      setCancellingJobId(null);
    }
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const typeLabel: Record<string, string> = {
    '.pdf': 'PDF',
    '.docx': 'Word',
    '.doc': 'Word',
    '.txt': 'TXT',
    '.md': 'Markdown',
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold dark:text-gray-100">资料库</h1>
        <div className="flex items-center gap-2">
          {selectMode ? (
            <button onClick={exitSelectMode} className="px-3 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">
              取消选择
            </button>
          ) : (
            <button onClick={() => setSelectMode(true)} className="px-3 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">
              批量操作
            </button>
          )}
          <FileUpload onUpload={handleUpload} onError={setError} maxSizeMb={50} />
        </div>
      </div>

      {/* Search */}
      <div className="flex gap-3 mb-6">
        <input
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
          placeholder="关键词检索资料内容..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <button
          onClick={handleSearch}
          disabled={searching || !query.trim()}
          className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {searching ? '搜索中...' : '搜索'}
        </button>
        {(hasSearched || query) && (
          <button
            onClick={handleClearSearch}
            className="px-5 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
          >
            清空
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {detailError && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">
          {detailError}
        </div>
      )}

      {/* Parse Jobs Section */}
      {parseJobs.length > 0 && (
        <div className="mb-6">
          <button
            onClick={() => setShowJobs(v => !v)}
            className="flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 mb-2"
          >
            <span>{showJobs ? '▼' : '▶'}</span>
            解析任务（{parseJobs.length}）
            {parseJobs.some(j => j.status === 'pending' || j.status === 'processing') && (
              <span className="inline-block w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            )}
          </button>
          {showJobs && (
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 space-y-2">
              {parseJobs.map(j => {
                const JOB_STATUS: Record<string, { label: string; color: string }> = {
                  pending: { label: '等待中', color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300' },
                  processing: { label: '处理中', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300' },
                  done: { label: '已完成', color: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
                  failed: { label: '失败', color: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' },
                  cancelled: { label: '已取消', color: 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400' },
                };
                const st = JOB_STATUS[j.status] || JOB_STATUS.done;
                const rawProgressPct = j.progress_total > 0 ? Math.round((j.progress_current / j.progress_total) * 100) : 0;
                const progressPct = Math.min(100, Math.max(0, rawProgressPct));
                const showProgress = j.status === 'processing' && j.progress_total > 0;
                const progressMsg = j.progress_message || (j.status === 'pending' ? '等待中' : '');
                return (
                  <div key={j.id} className="space-y-1">
                    <div className="flex items-center justify-between text-xs gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className={`px-1.5 py-0.5 rounded ${st.color}`}>{st.label}</span>
                        <span className="text-gray-700 dark:text-gray-300 truncate">{j.filename || `#${j.material_id}`}</span>
                        {j.attempts > 0 && <span className="text-gray-400">尝试 {j.attempts}</span>}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {progressMsg && !showProgress && (
                          <span className="text-gray-400">{progressMsg}</span>
                        )}
                        {j.error_message && (
                          <span className="text-red-400 truncate max-w-[200px]" title={j.error_message}>{j.error_message}</span>
                        )}
                        {j.created_at && (
                          <span className="text-gray-400">{new Date(j.created_at).toLocaleTimeString()}</span>
                        )}
                        {j.status === 'pending' && (
                          <button
                            onClick={() => handleCancelJob(j.id)}
                            disabled={cancellingJobId === j.id}
                            className="text-red-400 hover:text-red-600 disabled:opacity-50"
                          >
                            {cancellingJobId === j.id ? '取消中...' : '取消'}
                          </button>
                        )}
                        {j.status === 'processing' && (
                          <span className="text-blue-400 text-[10px]" title="正在解析中，暂不支持中断">无法取消</span>
                        )}
                        {j.status === 'failed' && (
                          <button
                            onClick={() => handleRetry(j.material_id)}
                            disabled={retryingId === j.material_id}
                            className="text-orange-500 hover:text-orange-700 disabled:opacity-50"
                          >
                            {retryingId === j.material_id ? '重试中...' : '重试'}
                          </button>
                        )}
                      </div>
                    </div>
                    {showProgress && (
                      <div className="flex items-center gap-2 pl-1">
                        <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all duration-300"
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-gray-400 shrink-0">{progressMsg}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Search Results */}
      {hasSearched && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">搜索结果（{results.length}）</h2>
          {results.length === 0 && !error ? (
            <p className="text-gray-400 text-sm">未找到相关资料</p>
          ) : (
            <div className="space-y-2">
              {results.map(r => (
                <button
                  key={r.material_id}
                  onClick={() => handleViewDetail(r.material_id, query)}
                  className="w-full text-left bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3 text-sm hover:bg-yellow-100 dark:hover:bg-yellow-900/30 transition-colors"
                >
                  <div className="font-medium text-gray-700 dark:text-gray-300">{r.filename}</div>
                  <div className="text-gray-500 dark:text-gray-400 mt-1"><HighlightedSnippet text={r.snippet} /></div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Material List */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg font-semibold">已上传资料</h2>
        {selectMode && materials.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              已选 {selectedIds.size} / {materials.length}
            </span>
            <button onClick={toggleSelectAll} className="text-sm text-blue-500 hover:text-blue-700">
              {selectedIds.size === materials.length ? '取消全选' : '全选'}
            </button>
            <button
              onClick={handleBulkDelete}
              disabled={selectedIds.size === 0 || bulkDeleting}
              className="px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm"
            >
              {bulkDeleting ? '删除中...' : `删除选中 (${selectedIds.size})`}
            </button>
            <button
              onClick={handleExportSelected}
              disabled={selectedIds.size === 0 || exportingSelected}
              className="px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm"
            >
              {exportingSelected ? '导出中...' : `导出选中 (${selectedIds.size})`}
            </button>
          </div>
        )}
      </div>
      {loadingMaterials ? (
        <p className="text-gray-400 text-sm">加载中...</p>
      ) : materials.length === 0 ? (
        <p className="text-gray-400 text-sm">暂无资料，点击右上角上传</p>
      ) : (
        <>
          <div className="grid gap-3">
            {materials.map(m => (
              <div key={m.id} className={`bg-white dark:bg-gray-800 rounded-lg shadow p-4 flex items-center justify-between ${deletingId === m.id ? 'opacity-50' : ''}`}>
                <div className="flex items-center gap-3">
                  {selectMode && (
                    <input
                      type="checkbox"
                      checked={selectedIds.has(m.id)}
                      onChange={() => toggleSelect(m.id)}
                      className="w-4 h-4 rounded border-gray-300 dark:border-gray-600"
                    />
                  )}
                  <span className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                    {typeLabel[m.file_type] || m.file_type}
                  </span>
                  <span className="text-sm text-gray-700 dark:text-gray-300">{m.filename}</span>
                  {(() => {
                    const st = STATUS_LABELS[m.status] || STATUS_LABELS.ready;
                    return <span className={`px-1.5 py-0.5 rounded text-[10px] ${st.color}`}>{st.label}</span>;
                  })()}
                  {m.status === 'failed' && m.error_message && (
                    <span className="text-[10px] text-red-400 truncate max-w-[200px]" title={m.error_message}>{m.error_message}</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">
                    {m.created_at ? new Date(m.created_at).toLocaleDateString() : ''}
                  </span>
                  {m.status === 'failed' && (
                    <button onClick={() => handleRetry(m.id)} disabled={retryingId === m.id} className="text-orange-500 hover:text-orange-700 disabled:opacity-50 text-sm">
                      {retryingId === m.id ? '重试中...' : '重试'}
                    </button>
                  )}
                  <button onClick={() => handleViewDetail(m.id)} disabled={detailLoadingId === m.id || deletingId === m.id} className="text-blue-500 hover:text-blue-700 disabled:opacity-50 text-sm">
                    {detailLoadingId === m.id ? '加载中...' : '查看'}
                  </button>
                  <button onClick={() => handleDelete(m.id)} disabled={deletingId === m.id} className="text-red-400 hover:text-red-600 disabled:opacity-50 text-sm">
                    {deletingId === m.id ? '删除中...' : '删除'}
                  </button>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 text-center">
            {hasMore ? (
              <button
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="px-5 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 text-sm"
              >
                {loadingMore ? '加载中...' : '加载更多'}
              </button>
            ) : (
              <p className="text-gray-400 text-sm">已加载全部资料</p>
            )}
          </div>
        </>
      )}

      {/* Detail Modal */}
      {selectedMaterial && (
        <MaterialDetailModal material={selectedMaterial} onClose={() => setSelectedMaterial(null)} initialQuery={detailInitialQuery} />
      )}
    </div>
  );
}
