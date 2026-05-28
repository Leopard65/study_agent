import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { uploadMaterial, listMaterials, searchMaterials, deleteMaterial, getMaterial, getApiErrorMessage } from '../api/client';
import type { MaterialItem, MaterialDetail, MaterialSearchResult } from '../api/client';
import FileUpload from '../components/FileUpload';

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
  const [searchParams, setSearchParams] = useSearchParams();
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
  const effectSeq = useRef(0);

  useEffect(() => {
    const seq = ++effectSeq.current;
    fetchFirstMaterials().then(items => {
      if (seq !== effectSeq.current) return;
      setMaterials(items);
      setHasMore(items.length === PAGE_SIZE);
    }).catch(err => {
      if (seq !== effectSeq.current) return;
      setError(getApiErrorMessage(err, '加载资料失败，请检查后端服务。'));
    }).finally(() => {
      if (seq !== effectSeq.current) return;
      setLoadingMaterials(false);
    });
    return () => { effectSeq.current += 1; };
  }, []);

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
  useEffect(() => {
    const openId = searchParams.get('open');
    if (openId) {
      const id = parseInt(openId, 10);
      if (!isNaN(id)) {
        setTimeout(() => {
          handleViewDetail(id).catch(() => {});
          setSearchParams({}, { replace: true });
        }, 0);
      }
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        <FileUpload onUpload={handleUpload} onError={setError} maxSizeMb={50} />
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
      <h2 className="text-lg font-semibold mb-3">已上传资料</h2>
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
