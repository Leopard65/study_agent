import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import type { MaterialDetail, ChunkItem } from '../api/client';
import { getMaterialChunks } from '../api/client';

const TYPE_LABEL: Record<string, string> = {
  '.pdf': 'PDF', '.docx': 'Word', '.doc': 'Word', '.txt': 'TXT', '.md': 'Markdown',
};

const CHUNKS_PAGE = 20;

/** 将 snippet 中的 >>>...<<< 标记渲染为高亮 */
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
    parts.push(<mark key={key++} className="bg-yellow-200 dark:bg-yellow-800 rounded px-0.5">{afterOpen.slice(0, end)}</mark>);
    remaining = afterOpen.slice(end + 3);
  }
  return <>{parts}</>;
}

/** 轻量文本高亮：对纯 content 中的 query 做高亮（无 >>><<< 标记时） */
function highlightPlainText(content: string, query: string): ReactNode {
  if (!query) return content;
  const idx = content.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return content;
  const before = content.slice(0, idx);
  const match = content.slice(idx, idx + query.length);
  const after = content.slice(idx + query.length);
  return <>{before}<mark className="bg-yellow-200 dark:bg-yellow-800 rounded px-0.5">{match}</mark>{after}</>;
}

interface MaterialDetailModalProps {
  material: MaterialDetail;
  onClose: () => void;
  initialQuery?: string;
}

export default function MaterialDetailModal({ material, onClose, initialQuery }: MaterialDetailModalProps) {
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [searchQuery, setSearchQuery] = useState(initialQuery || '');
  const [searchInput, setSearchInput] = useState(initialQuery || '');
  const scrollRef = useRef<HTMLDivElement>(null);

  const loadChunks = useCallback(async (query: string, offset: number, append: boolean) => {
    if (append) setLoadingMore(true);
    else setLoading(true);
    try {
      const params: { limit: number; offset: number; query?: string } = { limit: CHUNKS_PAGE, offset };
      if (query.trim()) params.query = query.trim();
      const items = await getMaterialChunks(material.id, params);
      setChunks(prev => append ? [...prev, ...items] : items);
      setHasMore(items.length === CHUNKS_PAGE);
    } catch {
      if (!append) setChunks([]);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [material.id]);

  // 初始加载 + searchQuery 变化时
  useEffect(() => {
    let cancelled = false;
    setLoading(true); // eslint-disable-line react-hooks/set-state-in-effect -- loading indicator for async fetch
    const params: { limit: number; offset: number; query?: string } = { limit: CHUNKS_PAGE, offset: 0 };
    if (searchQuery.trim()) params.query = searchQuery.trim();
    getMaterialChunks(material.id, params)
      .then(items => {
        if (!cancelled) { setChunks(items); setHasMore(items.length === CHUNKS_PAGE); }
      })
      .catch(() => { if (!cancelled) setChunks([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [searchQuery, material.id]);

  // 当 initialQuery prop 变化时同步到内部状态（同一弹窗复用场景）
  const prevInitialRef = useRef(initialQuery);
  useEffect(() => {
    if (initialQuery !== prevInitialRef.current) {
      prevInitialRef.current = initialQuery;
      if (initialQuery !== undefined) {
        setSearchInput(initialQuery); // eslint-disable-line react-hooks/set-state-in-effect -- prop sync
        setSearchQuery(initialQuery);
      }
    }
  }, [initialQuery]);

  const handleSearch = () => {
    if (searchInput.trim() === searchQuery.trim()) return;
    setSearchQuery(searchInput.trim());
  };

  const handleLoadMore = () => {
    loadChunks(searchQuery, chunks.length, true);
  };

  const isReady = material.status === 'ready';
  const hasChunks = chunks.length > 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b dark:border-gray-700">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 truncate">{material.filename}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 text-xl ml-4">&times;</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto" ref={scrollRef}>
          {/* Meta info */}
          <div className="px-6 pt-4 pb-3 flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-400 border-b dark:border-gray-700">
            <span>类型：{TYPE_LABEL[material.file_type] || material.file_type}</span>
            <span>上传：{material.created_at ? new Date(material.created_at).toLocaleString() : '未知'}</span>
            <span>文本：{material.content_length.toLocaleString()} 字符</span>
            {material.status !== 'ready' && (
              <span className={material.status === 'failed' ? 'text-red-500' : 'text-yellow-500'}>
                状态：{material.status === 'failed' ? '解析失败' : material.status === 'pending' ? '等待解析' : material.status === 'processing' ? '解析中' : material.status}
              </span>
            )}
            {material.status === 'failed' && material.error_message && (
              <span className="text-red-400 text-xs truncate max-w-xs" title={material.error_message}>{material.error_message}</span>
            )}
          </div>

          {/* In-material search */}
          {isReady && (
            <div className="px-6 py-3 flex gap-2 border-b dark:border-gray-700">
              <input
                className="flex-1 border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                placeholder="在资料内搜索..."
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
              />
              <button
                onClick={handleSearch}
                className="px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                搜索
              </button>
              {searchQuery && (
                <button
                  onClick={() => { setSearchInput(''); setSearchQuery(''); }}
                  className="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"
                >
                  清除
                </button>
              )}
            </div>
          )}

          {/* Content area */}
          <div className="px-6 py-4">
            {!isReady ? (
              <p className="text-gray-400 text-sm">
                {material.status === 'pending' ? '资料等待解析...' :
                 material.status === 'processing' ? '资料正在解析中...' :
                 '暂无可预览文本，可能是文件解析失败或扫描版 PDF OCR 未识别到文字。'}
              </p>
            ) : loading ? (
              <p className="text-gray-400 text-sm">加载中...</p>
            ) : !hasChunks ? (
              <p className="text-gray-400 text-sm">
                {searchQuery ? `未找到包含「${searchQuery}」的内容` : '暂无分块内容'}
              </p>
            ) : (
              <div className="space-y-3">
                {searchQuery && (
                  <p className="text-xs text-gray-400 mb-2">
                    找到 {chunks.length} 个匹配片段{hasMore ? '（还有更多）' : ''}
                  </p>
                )}
                {chunks.map(c => (
                  <div key={c.id} className="border dark:border-gray-700 rounded-lg overflow-hidden">
                    <div className="px-3 py-1.5 bg-gray-50 dark:bg-gray-750 text-[10px] text-gray-400 flex items-center justify-between">
                      <span>段落 #{c.chunk_index + 1}</span>
                      <span className="text-gray-300">{c.content.length} 字符</span>
                    </div>
                    <div className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap max-h-48 overflow-y-auto">
                      {searchQuery && c.snippet ? (
                        <HighlightedSnippet text={c.snippet} />
                      ) : searchQuery ? (
                        highlightPlainText(c.content, searchQuery)
                      ) : (
                        c.content
                      )}
                    </div>
                  </div>
                ))}
                {hasMore && (
                  <button
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="w-full py-2 text-sm text-blue-500 hover:text-blue-700 disabled:opacity-50"
                  >
                    {loadingMore ? '加载中...' : '加载更多'}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
