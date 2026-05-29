import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { uploadMaterial, listMaterials, searchMaterials, deleteMaterial, getMaterial, bulkDeleteMaterials, exportSelectedMaterials, getApiErrorMessage } from '../api/client';
import type { MaterialItem, MaterialDetail, MaterialSearchResult } from '../api/client';
import FileUpload from '../components/FileUpload';
import { useSafeAsync } from '../hooks/useSafeAsync';
import { useDeepLink } from '../hooks/useDeepLink';

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

  // Bulk operations
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [exportingSelected, setExportingSelected] = useState(false);

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
    return cancel;
  }, [run, cancel]);

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

  const handleViewDetail = async (id: number) => {
    setDetailError('');
    setDetailLoadingId(id);
    try {
      const detail = await getMaterial(id);
      setSelectedMaterial(detail);
    } catch (err) {
      setDetailError(getApiErrorMessage(err, '加载资料详情失败，请检查后端服务。'));
    } finally {
      setDetailLoadingId(null);
    }
  };

  // Deep link: auto-open material detail
  useDeepLink((id) => handleViewDetail(id).catch(() => {}));

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
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `math_agent_materials_${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(getApiErrorMessage(err, '导出失败，请检查后端服务。'));
    } finally {
      setExportingSelected(false);
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

      {/* Search Results */}
      {hasSearched && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">搜索结果（{results.length}）</h2>
          {results.length === 0 && !error ? (
            <p className="text-gray-400 text-sm">未找到相关资料</p>
          ) : (
            <div className="space-y-2">
              {results.map(r => (
                <div key={r.material_id} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
                  <div className="font-medium text-gray-700">{r.filename}</div>
                  <div className="text-gray-500 mt-1"><HighlightedSnippet text={r.snippet} /></div>
                </div>
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
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">
                    {m.created_at ? new Date(m.created_at).toLocaleDateString() : ''}
                  </span>
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
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedMaterial(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 truncate">{selectedMaterial.filename}</h3>
              <button onClick={() => setSelectedMaterial(null)} className="text-gray-400 hover:text-gray-600 text-xl ml-4">&times;</button>
            </div>
            <div className="px-6 py-4 overflow-y-auto flex-1">
              <div className="flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-400 mb-4">
                <span>文件类型：{typeLabel[selectedMaterial.file_type] || selectedMaterial.file_type}</span>
                <span>上传时间：{selectedMaterial.created_at ? new Date(selectedMaterial.created_at).toLocaleString() : '未知'}</span>
                {selectedMaterial.stored_filename && <span>存储文件名：{selectedMaterial.stored_filename}</span>}
                <span>文本长度：{selectedMaterial.content_length} 字符</span>
              </div>
              <div className="text-sm text-gray-700 dark:text-gray-300">
                {selectedMaterial.preview ? (
                  <>
                    <pre className="whitespace-pre-wrap bg-gray-50 rounded p-4 max-h-96 overflow-y-auto text-sm leading-relaxed">
                      {selectedMaterial.preview}
                    </pre>
                    {selectedMaterial.truncated && (
                      <p className="text-gray-400 text-xs mt-2">仅显示前 {selectedMaterial.preview.length} 字符预览</p>
                    )}
                  </>
                ) : (
                  <p className="text-gray-400">暂无可预览文本，可能是文件解析失败或扫描版 PDF OCR 未识别到文字。</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
