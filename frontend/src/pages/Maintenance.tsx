import { useEffect, useState } from 'react';
import {
  getMaintenanceHealth, getCleanupPreview, executeCleanup, getOperationLogs,
  getApiErrorMessage,
} from '../api/client';
import type { MaintenanceHealth, CleanupPreview, CleanupResult, OperationLogItem } from '../api/client';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

const OP_LABELS: Record<string, string> = {
  export_json: '导出 JSON',
  export_zip: '导出 ZIP',
  import_json: '导入 JSON',
  import_zip: '导入 ZIP',
  cleanup: '数据清理',
};

export default function Maintenance() {
  const [health, setHealth] = useState<MaintenanceHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [preview, setPreview] = useState<CleanupPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [cleaning, setCleaning] = useState(false);
  const [cleanupResult, setCleanupResult] = useState<CleanupResult | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const [logs, setLogs] = useState<OperationLogItem[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const h = await getMaintenanceHealth();
      setHealth(h);
      setError('');
    } catch (err) {
      setError(getApiErrorMessage(err, '加载健康数据失败'));
    } finally {
      setLoading(false);
    }
  };

  const fetchLogs = async () => {
    setLogsLoading(true);
    try {
      const l = await getOperationLogs(20);
      setLogs(l);
    } catch {
      // silently ignore
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const h = await getMaintenanceHealth();
        if (!cancelled) { setHealth(h); setError(''); }
      } catch (err) {
        if (!cancelled) setError(getApiErrorMessage(err, '加载健康数据失败'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    (async () => {
      setLogsLoading(true);
      try {
        const l = await getOperationLogs(20);
        if (!cancelled) setLogs(l);
      } catch { /* ignore */ } finally {
        if (!cancelled) setLogsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handlePreview = async () => {
    setPreviewLoading(true);
    setCleanupResult(null);
    try {
      const p = await getCleanupPreview();
      setPreview(p);
    } catch (err) {
      setError(getApiErrorMessage(err, '预览清理失败'));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleCleanup = async () => {
    setShowConfirm(false);
    setCleaning(true);
    try {
      const r = await executeCleanup();
      setCleanupResult(r);
      setPreview(null);
      // Refresh health and logs
      fetchHealth();
      fetchLogs();
    } catch (err) {
      setError(getApiErrorMessage(err, '清理失败'));
    } finally {
      setCleaning(false);
    }
  };

  const hasIssues = health && (health.orphan_files > 0 || health.missing_files > 0 || health.failed_materials > 0 || health.failed_jobs > 0);

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto">
      <h1 className="text-xl font-bold mb-4 text-gray-900 dark:text-gray-100">数据维护中心</h1>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 rounded text-red-700 dark:text-red-300 text-sm">
          {error}
          <button onClick={() => setError('')} className="ml-2 underline">关闭</button>
        </div>
      )}

      {/* Health Summary */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-3 text-gray-800 dark:text-gray-200">数据健康摘要</h2>
        {loading ? (
          <div className="text-gray-500 text-sm">加载中…</div>
        ) : health ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="资料记录" value={health.total_materials} />
            <StatCard label="分块索引" value={health.total_chunks} />
            <StatCard label="上传文件" value={health.upload_files} />
            <StatCard label="数据库大小" value={formatBytes(health.database_size)} />
            <StatCard label="上传目录大小" value={formatBytes(health.uploads_size)} />
            <StatCard label="解析失败" value={health.failed_materials} highlight={health.failed_materials > 0} />
            <StatCard label="孤儿文件" value={health.orphan_files} highlight={health.orphan_files > 0} />
            <StatCard label="缺失文件" value={health.missing_files} highlight={health.missing_files > 0} />
          </div>
        ) : null}

        {health && health.orphan_files > 0 && (
          <div className="mt-3 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded text-sm text-yellow-800 dark:text-yellow-300">
            发现 {health.orphan_files} 个孤儿文件（存在于 uploads 目录但未被资料引用），可安全清理。
            {health.orphan_file_names.length > 0 && (
              <span className="text-gray-500 ml-1">例: {health.orphan_file_names.slice(0, 3).join(', ')}</span>
            )}
          </div>
        )}
        {health && health.missing_files > 0 && (
          <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded text-sm text-red-800 dark:text-red-300">
            {health.missing_files} 个资料记录引用的文件在 uploads 目录中缺失，资料预览和搜索将不可用。
            建议从备份 ZIP 恢复。
          </div>
        )}
        {health && health.failed_materials > 0 && (
          <div className="mt-2 p-2 bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700 rounded text-sm text-orange-800 dark:text-orange-300">
            {health.failed_materials} 个资料解析失败。可在资料库中重试解析。
          </div>
        )}
        {health && !hasIssues && (
          <div className="mt-3 p-2 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded text-sm text-green-800 dark:text-green-300">
            ✅ 数据状态良好，无需清理。
          </div>
        )}
      </section>

      {/* Cleanup */}
      <section className="mb-6">
        <h2 className="text-lg font-semibold mb-3 text-gray-800 dark:text-gray-200">安全清理</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
          清理孤儿文件（uploads 目录中未被引用的文件）和无效解析任务。不会删除任何被资料引用的文件。
        </p>
        <div className="flex gap-2 mb-3">
          <button
            onClick={handlePreview}
            disabled={previewLoading || cleaning}
            className="px-4 py-2 bg-gray-600 text-white rounded text-sm hover:bg-gray-500 disabled:opacity-50"
          >
            {previewLoading ? '预览中...' : '预览清理'}
          </button>
          {preview && (preview.orphan_files_count > 0 || preview.invalid_jobs_count > 0 || preview.orphan_chunk_materials_count > 0) && (
            <button
              onClick={() => setShowConfirm(true)}
              disabled={cleaning}
              className="px-4 py-2 bg-orange-600 text-white rounded text-sm hover:bg-orange-500 disabled:opacity-50"
            >
              {cleaning ? '清理中...' : '确认清理'}
            </button>
          )}
        </div>

        {preview && (
          <div className="p-3 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded text-sm">
            <div className="font-medium mb-2">清理预览：</div>
            <ul className="space-y-1 text-gray-700 dark:text-gray-300">
              <li>🗑️ 孤儿文件: {preview.orphan_files_count} 个{preview.orphan_files_count > 0 && ` (${preview.orphan_files.slice(0, 5).join(', ')}${preview.orphan_files_count > 5 ? '...' : ''})`}</li>
              <li>🔧 无效解析任务: {preview.invalid_jobs_count} 个</li>
              <li>📦 孤儿分块: {preview.orphan_chunk_materials_count} 组</li>
            </ul>
            {preview.orphan_files_count === 0 && preview.invalid_jobs_count === 0 && preview.orphan_chunk_materials_count === 0 && (
              <div className="text-green-600 dark:text-green-400 mt-1">无需清理，数据状态良好。</div>
            )}
          </div>
        )}

        {/* Confirm modal */}
        {showConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowConfirm(false)}>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 max-w-sm mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
              <div className="font-bold mb-2 text-gray-900 dark:text-gray-100">确认清理？</div>
              <div className="text-sm text-gray-600 dark:text-gray-300 mb-3">
                将删除 {preview?.orphan_files_count || 0} 个孤儿文件、{preview?.invalid_jobs_count || 0} 个无效任务、{preview?.orphan_chunk_materials_count || 0} 组孤儿分块。
                此操作不可撤销。
              </div>
              <div className="flex gap-2">
                <button onClick={handleCleanup} disabled={cleaning} className="flex-1 px-3 py-1.5 bg-orange-600 text-white rounded text-sm hover:bg-orange-700 disabled:opacity-50">
                  {cleaning ? '清理中...' : '确认清理'}
                </button>
                <button onClick={() => setShowConfirm(false)} disabled={cleaning} className="flex-1 px-3 py-1.5 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded text-sm hover:bg-gray-400 dark:hover:bg-gray-500 disabled:opacity-50">
                  取消
                </button>
              </div>
            </div>
          </div>
        )}

        {cleanupResult && (
          <div className="mt-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-700 rounded text-sm">
            <div className="font-medium text-green-800 dark:text-green-300 mb-1">清理完成</div>
            <ul className="space-y-0.5 text-green-700 dark:text-green-400">
              <li>已删除 {cleanupResult.deleted_files.length} 个孤儿文件</li>
              <li>已删除 {cleanupResult.deleted_jobs} 个无效解析任务</li>
              <li>已删除 {cleanupResult.deleted_chunks} 组孤儿分块</li>
              {cleanupResult.skipped_files.length > 0 && <li>跳过 {cleanupResult.skipped_files.length} 个文件（扩展名不在允许列表）</li>}
              {cleanupResult.errors.length > 0 && <li className="text-red-600">{cleanupResult.errors.length} 个错误</li>}
            </ul>
          </div>
        )}
      </section>

      {/* Operation Logs */}
      <section>
        <h2 className="text-lg font-semibold mb-3 text-gray-800 dark:text-gray-200">操作记录</h2>
        {logsLoading ? (
          <div className="text-gray-500 text-sm">加载中…</div>
        ) : logs.length === 0 ? (
          <div className="text-gray-500 text-sm">暂无操作记录。</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-left text-gray-600 dark:text-gray-400">
                  <th className="py-2 pr-3">时间</th>
                  <th className="py-2 pr-3">操作</th>
                  <th className="py-2 pr-3">类型</th>
                  <th className="py-2 pr-3">策略</th>
                  <th className="py-2">摘要</th>
                </tr>
              </thead>
              <tbody>
                {logs.map(log => (
                  <tr key={log.id} className="border-b border-gray-100 dark:border-gray-800 text-gray-700 dark:text-gray-300">
                    <td className="py-2 pr-3 whitespace-nowrap">{log.created_at ? new Date(log.created_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '-'}</td>
                    <td className="py-2 pr-3">{OP_LABELS[log.operation_type] || log.operation_type}</td>
                    <td className="py-2 pr-3">{log.file_type || '-'}</td>
                    <td className="py-2 pr-3">{log.strategy || '-'}</td>
                    <td className="py-2 max-w-xs truncate" title={log.result_summary}>{log.result_summary || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className={`p-3 rounded border ${highlight ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-300 dark:border-yellow-700' : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700'}`}>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-lg font-bold ${highlight ? 'text-yellow-700 dark:text-yellow-300' : 'text-gray-900 dark:text-gray-100'}`}>{value}</div>
    </div>
  );
}
