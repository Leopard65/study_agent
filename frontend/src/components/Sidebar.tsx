import { useEffect, useRef, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { usePreferences } from '../hooks/usePreferences';
import { getHealth, exportJson, exportZip, importPreview, importJson, importZipPreview, importZip, getApiErrorMessage } from '../api/client';
import type { HealthStatus, ImportPreview, ImportResult, ZipImportPreview, ZipImportResult } from '../api/client';
import { downloadBlob } from '../utils/constants';

const links = [
  { to: '/', label: '学习工作台', icon: '📊' },
  { to: '/qa', label: 'AI 问答', icon: '💬' },
  { to: '/materials', label: '资料库', icon: '📚' },
  { to: '/problems', label: '题目解析', icon: '✏️' },
  { to: '/errors', label: '错题本', icon: '📝' },
  { to: '/plan', label: '学习计划', icon: '📅' },
  { to: '/exam', label: '真题练习', icon: '📋' },
  { to: '/review', label: '今日复习', icon: '🔄' },
  { to: '/search', label: '全局搜索', icon: '🔍' },
  { to: '/maintenance', label: '数据维护', icon: '🛠️' },
];

const MODULE_LABELS: Record<string, string> = {
  materials: '资料', error_book: '错题', study_plans: '计划',
  problems: '解析', chat_history: '问答', exam_questions: '真题',
  app_settings: '复习设置', study_sessions: '学习会话',
};

const THEME_OPTIONS: { value: 'light' | 'dark' | 'system'; label: string; icon: string }[] = [
  { value: 'light', label: '浅色', icon: '☀️' },
  { value: 'dark', label: '深色', icon: '🌙' },
  { value: 'system', label: '跟随系统', icon: '💻' },
];

interface SidebarProps {
  onOpenPalette: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export default function Sidebar({ onOpenPalette, mobileOpen, onMobileClose }: SidebarProps) {
  const { sidebarCollapsed, theme, setSidebarCollapsed, setTheme } = usePreferences();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportingZip, setExportingZip] = useState(false);
  const [exportError, setExportError] = useState('');

  // Import state (JSON)
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [importData, setImportData] = useState<Record<string, unknown> | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importStrategy, setImportStrategy] = useState<'skip' | 'overwrite' | 'keep_both'>('skip');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showOverwriteConfirm, setShowOverwriteConfirm] = useState(false);
  const previewRequestId = useRef(0);

  // Import state (ZIP)
  const [zipImporting, setZipImporting] = useState(false);
  const [zipImportError, setZipImportError] = useState('');
  const [zipPreview, setZipPreview] = useState<ZipImportPreview | null>(null);
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [zipImportResult, setZipImportResult] = useState<ZipImportResult | null>(null);
  const [zipImportStrategy, setZipImportStrategy] = useState<'skip' | 'overwrite' | 'keep_both'>('skip');
  const [zipPreviewLoading, setZipPreviewLoading] = useState(false);
  const [showZipOverwriteConfirm, setShowZipOverwriteConfirm] = useState(false);
  const zipPreviewRequestId = useRef(0);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {}).finally(() => setChecking(false));
  }, []);

  const handleExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      const blob = await exportJson();
      const date = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `math_agent_backup_${date}.json`);
    } catch (err) {
      setExportError(getApiErrorMessage(err, '导出失败，请检查后端服务。'));
    } finally {
      setExporting(false);
    }
  };

  const handleExportZip = async () => {
    setExportingZip(true);
    setExportError('');
    try {
      const blob = await exportZip();
      const date = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `math_agent_backup_${date}.zip`);
    } catch (err) {
      setExportError(getApiErrorMessage(err, '导出 ZIP 失败，请检查后端服务。'));
    } finally {
      setExportingZip(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError('');
    setPreview(null);
    setImportResult(null);
    setPreviewLoading(true);
    const reqId = ++previewRequestId.current;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      setImportData(data);
      const p = await importPreview(data, importStrategy);
      if (reqId === previewRequestId.current) {
        setPreview(p);
        setImportError('');
      }
    } catch (err) {
      if (reqId === previewRequestId.current) {
        setImportError(getApiErrorMessage(err, '读取备份文件失败，请确认文件格式。'));
      }
    } finally {
      if (reqId === previewRequestId.current) {
        setPreviewLoading(false);
      }
      e.target.value = '';
    }
  };

  const handleStrategyChange = async (newStrategy: 'skip' | 'overwrite' | 'keep_both') => {
    setImportStrategy(newStrategy);
    if (importData) {
      setPreviewLoading(true);
      const reqId = ++previewRequestId.current;
      try {
        const p = await importPreview(importData, newStrategy);
        if (reqId === previewRequestId.current) {
          setPreview(p);
          setImportError('');
        }
      } catch (err) {
        if (reqId === previewRequestId.current) {
          setImportError(getApiErrorMessage(err, '刷新预览失败。'));
        }
      } finally {
        if (reqId === previewRequestId.current) {
          setPreviewLoading(false);
        }
      }
    }
  };

  const handleImportClick = () => {
    if (!importData) return;
    // Overwrite with conflicts needs double confirmation
    if (importStrategy === 'overwrite' && preview && preview.total_conflicts > 0) {
      setShowOverwriteConfirm(true);
      return;
    }
    doImport();
  };

  const doImport = async () => {
    if (!importData) return;
    setShowOverwriteConfirm(false);
    setImporting(true);
    setImportError('');
    try {
      const result = await importJson(importData, importStrategy);
      setImportResult(result);
      setPreview(null);
      setImportData(null);
    } catch (err) {
      setImportError(getApiErrorMessage(err, '导入失败，请检查后端服务。'));
    } finally {
      setImporting(false);
    }
  };

  // ── ZIP import handlers ──
  const handleZipFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setZipImportError('');
    setZipPreview(null);
    setZipImportResult(null);
    setZipFile(file);
    setZipPreviewLoading(true);
    const reqId = ++zipPreviewRequestId.current;
    try {
      const p = await importZipPreview(file, zipImportStrategy);
      if (reqId === zipPreviewRequestId.current) {
        setZipPreview(p);
        setZipImportError('');
      }
    } catch (err) {
      if (reqId === zipPreviewRequestId.current) {
        setZipImportError(getApiErrorMessage(err, '读取 ZIP 备份失败，请确认文件格式。'));
      }
    } finally {
      if (reqId === zipPreviewRequestId.current) {
        setZipPreviewLoading(false);
      }
      e.target.value = '';
    }
  };

  const handleZipStrategyChange = async (newStrategy: 'skip' | 'overwrite' | 'keep_both') => {
    setZipImportStrategy(newStrategy);
    if (zipFile) {
      setZipPreviewLoading(true);
      const reqId = ++zipPreviewRequestId.current;
      try {
        const p = await importZipPreview(zipFile, newStrategy);
        if (reqId === zipPreviewRequestId.current) {
          setZipPreview(p);
          setZipImportError('');
        }
      } catch (err) {
        if (reqId === zipPreviewRequestId.current) {
          setZipImportError(getApiErrorMessage(err, '刷新预览失败。'));
        }
      } finally {
        if (reqId === zipPreviewRequestId.current) {
          setZipPreviewLoading(false);
        }
      }
    }
  };

  const handleZipImportClick = () => {
    if (!zipFile) return;
    if (zipImportStrategy === 'overwrite' && zipPreview && zipPreview.total_conflicts > 0) {
      setShowZipOverwriteConfirm(true);
      return;
    }
    doZipImport();
  };

  const doZipImport = async () => {
    if (!zipFile) return;
    setShowZipOverwriteConfirm(false);
    setZipImporting(true);
    setZipImportError('');
    try {
      const result = await importZip(zipFile, zipImportStrategy);
      setZipImportResult(result);
      setZipPreview(null);
      setZipFile(null);
    } catch (err) {
      setZipImportError(getApiErrorMessage(err, '导入 ZIP 失败，请检查后端服务。'));
    } finally {
      setZipImporting(false);
    }
  };

  let statusText = '运行正常';
  let statusColor = 'text-green-400';
  if (checking) {
    statusText = '检查中…';
    statusColor = 'text-gray-500';
  } else if (!health) {
    statusText = '后端未启动';
    statusColor = 'text-red-400';
  } else if (health.status !== 'ok') {
    statusText = '后端异常';
    statusColor = 'text-red-400';
  } else if (!health.ai_configured) {
    statusText = '需配置 API Key';
    statusColor = 'text-yellow-400';
  }

  const w = sidebarCollapsed ? 'w-16' : 'w-56';
  const handleNavClick = () => onMobileClose?.();

  return (
    <>
    {/* Mobile overlay */}
    {mobileOpen && (
      <div
        className="fixed inset-0 z-40 bg-black/50 md:hidden"
        onClick={onMobileClose}
      />
    )}

    <aside className={`
      ${w} bg-gray-900 text-gray-100 flex flex-col transition-all duration-200
      md:relative md:min-h-screen md:shrink-0
      fixed inset-y-0 left-0 z-40 md:z-auto
      ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
    `}>
      {/* Header */}
      <div className={`py-5 border-b border-gray-700 flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'justify-between px-4'}`}>
        {!sidebarCollapsed && <span className="text-lg font-bold">考研学习助手</span>}
        <div className="flex items-center gap-1">
          {/* Mobile close button */}
          <button
            onClick={onMobileClose}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200 md:hidden"
            aria-label="关闭菜单"
          >
            ✕
          </button>
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-gray-200 hidden md:block"
            title={sidebarCollapsed ? '展开侧边栏' : '折叠侧边栏'}
          >
            {sidebarCollapsed ? '▶' : '◀'}
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2">
        {links.map(l => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === '/'}
            title={sidebarCollapsed ? l.label : undefined}
            onClick={handleNavClick}
            className={({ isActive }) =>
              `flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'gap-3 px-4'} py-2.5 text-sm transition-colors ${
                isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'
              }`
            }
          >
            <span className="text-base">{l.icon}</span>
            {!sidebarCollapsed && <span>{l.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className={`py-3 text-xs border-t border-gray-700 ${sidebarCollapsed ? 'px-2' : 'px-4'}`}>
        {/* Command palette */}
        <button
          onClick={onOpenPalette}
          className={`w-full px-3 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 text-xs flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}
          title="命令面板 (Ctrl+K)"
        >
          {sidebarCollapsed ? '⌨' : (
            <>
              <span>命令面板</span>
              <kbd className="px-1 py-0.5 bg-gray-600 rounded text-[10px]">Ctrl+K</kbd>
            </>
          )}
        </button>

        {/* Theme selector */}
        <div className={`mt-2 flex ${sidebarCollapsed ? 'flex-col items-center gap-1' : 'gap-1'}`}>
          {THEME_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              className={`px-1.5 py-1 rounded text-[10px] ${theme === opt.value ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'}`}
              title={opt.label}
            >
              {sidebarCollapsed ? opt.icon : opt.label}
            </button>
          ))}
        </div>

        {!sidebarCollapsed && (
          <>
            <div className="text-gray-500 mt-2">MVP v0.7</div>
            <div className={`mt-1 ${statusColor}`}>{statusText}</div>
          </>
        )}
        {sidebarCollapsed && (
          <div className={`mt-1 text-center ${statusColor}`} title={statusText}>
            {checking ? '⏳' : !health || health.status !== 'ok' ? '❌' : !health.ai_configured ? '⚠️' : '✅'}
          </div>
        )}

        {/* Export */}
        <div className={`mt-2 flex gap-1 ${sidebarCollapsed ? 'flex-col' : ''}`}>
          <button
            onClick={handleExport}
            disabled={exporting || exportingZip || importing || previewLoading || zipImporting || zipPreviewLoading}
            className={`flex-1 px-2 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50 text-xs ${sidebarCollapsed ? 'px-1' : ''}`}
            title="导出仅数据 (JSON)"
          >
            {sidebarCollapsed ? '📄' : (exporting ? '...' : '数据 JSON')}
          </button>
          <button
            onClick={handleExportZip}
            disabled={exporting || exportingZip || importing || previewLoading || zipImporting || zipPreviewLoading}
            className={`flex-1 px-2 py-1.5 bg-blue-700 text-gray-300 rounded hover:bg-blue-600 disabled:opacity-50 text-xs ${sidebarCollapsed ? 'px-1' : ''}`}
            title="导出完整备份 ZIP（含上传文件）"
          >
            {sidebarCollapsed ? '📦' : (exportingZip ? '...' : '完整 ZIP')}
          </button>
        </div>
        {!sidebarCollapsed && exportError && <div className="mt-1 text-red-400">{exportError}</div>}

        {/* Import */}
        <div className={`mt-1.5 flex gap-1 ${sidebarCollapsed ? 'flex-col' : ''}`}>
          <label
            className={`flex-1 px-2 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 text-xs text-center cursor-pointer block ${sidebarCollapsed ? 'px-1' : ''} ${(importing || previewLoading || zipImporting || zipPreviewLoading) ? 'opacity-50 pointer-events-none' : ''}`}
            title="导入数据 JSON"
          >
            {sidebarCollapsed ? '📄' : (importing ? '...' : previewLoading ? '...' : '导入 JSON')}
            <input type="file" accept=".json" className="hidden" onChange={handleFileSelect} disabled={importing || previewLoading || zipImporting || zipPreviewLoading} />
          </label>
          <label
            className={`flex-1 px-2 py-1.5 bg-blue-700 text-gray-300 rounded hover:bg-blue-600 text-xs text-center cursor-pointer block ${sidebarCollapsed ? 'px-1' : ''} ${(importing || previewLoading || zipImporting || zipPreviewLoading) ? 'opacity-50 pointer-events-none' : ''}`}
            title="导入完整备份 ZIP"
          >
            {sidebarCollapsed ? '📦' : (zipImporting ? '...' : zipPreviewLoading ? '...' : '导入 ZIP')}
            <input type="file" accept=".zip" className="hidden" onChange={handleZipFileSelect} disabled={importing || previewLoading || zipImporting || zipPreviewLoading} />
          </label>
        </div>
        {!sidebarCollapsed && importError && <div className="mt-1 text-red-400">{importError}</div>}
        {!sidebarCollapsed && zipImportError && <div className="mt-1 text-red-400">{zipImportError}</div>}

        {/* Import preview/result - only in expanded mode */}
        {!sidebarCollapsed && preview && (
          <div className="mt-2 p-2 bg-gray-800 rounded text-xs space-y-0.5">
            <div className="text-gray-400 mb-1 flex items-center gap-1">
              备份预览（{preview.exported_at?.slice(0, 10)}）
              {previewLoading && <span className="text-blue-400 animate-pulse">刷新中...</span>}
            </div>
            <div>错题: {preview.error_book_count} / 计划: {preview.study_plans_count}</div>
            <div>真题: {preview.exam_questions_count} / 答题: {preview.exam_attempts_count}</div>
            <div>资料: {preview.materials_count} / 问答: {preview.chat_history_count}</div>
            <div>解析: {preview.problems_count} / 设置: {preview.app_settings_count ?? 0} / 会话: {preview.study_sessions_count ?? 0}</div>
            {(preview.settings_invalid ?? 0) > 0 && (
              <div className="text-yellow-400">{preview.settings_invalid} 项设置数据无效，将跳过</div>
            )}
            {(preview.sessions_invalid ?? 0) > 0 && (
              <div className="text-yellow-400">{preview.sessions_invalid} 条会话数据无效，将跳过</div>
            )}

            {/* Conflict summary */}
            {preview.total_conflicts > 0 && (
              <div className="mt-1.5 pt-1.5 border-t border-gray-700 text-yellow-400">
                检测到 {preview.total_conflicts} 条冲突数据
              </div>
            )}

            {/* Per-module conflict details */}
            {preview.total_conflicts > 0 && (
              <div className="mt-1 space-y-0.5">
                {Object.entries(preview.modules).filter(([, s]) => s.conflict_count > 0).map(([mod, s]) => {
                  const action = s.would_skip > 0 ? `跳过${s.would_skip}` :
                    s.would_overwrite > 0 ? `覆盖${s.would_overwrite}` :
                    s.would_keep_both > 0 ? `保留${s.would_keep_both}` : '';
                  return (
                    <div key={mod} className="flex justify-between">
                      <span>{MODULE_LABELS[mod] || mod}:</span>
                      <span className="text-gray-400">新增{s.new_count} / 冲突{s.conflict_count} → {action}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Conflict samples */}
            {Object.keys(preview.conflict_samples).length > 0 && (
              <div className="mt-1 text-gray-500">
                {Object.entries(preview.conflict_samples).map(([mod, samples]) => {
                  return (
                    <div key={mod}>
                      {MODULE_LABELS[mod]}冲突项: {samples.map(s => `"${s}"`).join(', ')}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Strategy selector */}
            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="text-gray-400 mb-1">冲突策略：</div>
              <div className="flex flex-col gap-1">
                {(['skip', 'overwrite', 'keep_both'] as const).map(s => (
                  <label key={s} className={`flex items-center gap-1.5 ${previewLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
                    <input type="radio" name="import-strategy" value={s}
                      checked={importStrategy === s}
                      onChange={() => handleStrategyChange(s)}
                      disabled={previewLoading || importing}
                      className="accent-blue-500" />
                    <span>{s === 'skip' ? '跳过（保留现有数据）' : s === 'overwrite' ? '覆盖（用导入数据替换）' : '保留两份（自动重命名）'}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Overwrite warning */}
            {importStrategy === 'overwrite' && preview.total_conflicts > 0 && (
              <div className="mt-1.5 p-1.5 bg-red-900/40 border border-red-700 rounded text-red-300">
                警告：覆盖策略将替换 {preview.total_conflicts} 条现有数据，此操作不可撤销！
              </div>
            )}

            <div className="flex gap-2 mt-2">
              <button onClick={handleImportClick} disabled={importing || previewLoading} className="flex-1 px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
                {importing ? '导入中...' : '确认导入'}
              </button>
              <button onClick={() => { setPreview(null); setImportData(null); setImportError(''); }} disabled={importing} className="flex-1 px-2 py-1 bg-gray-600 text-gray-300 rounded text-xs hover:bg-gray-500 disabled:opacity-50">
                取消
              </button>
            </div>
          </div>
        )}

        {/* Overwrite confirmation modal */}
        {showOverwriteConfirm && preview && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowOverwriteConfirm(false)}>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 max-w-xs mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
              <div className="text-red-600 dark:text-red-400 font-bold mb-2">确认覆盖导入？</div>
              <div className="text-sm text-gray-700 dark:text-gray-300 mb-3">
                将覆盖 {preview.total_conflicts} 条现有数据，此操作不可撤销。
              </div>
              <div className="flex gap-2">
                <button onClick={doImport} disabled={importing} className="flex-1 px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50">
                  {importing ? '导入中...' : '确认覆盖'}
                </button>
                <button onClick={() => setShowOverwriteConfirm(false)} disabled={importing} className="flex-1 px-3 py-1.5 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded text-sm hover:bg-gray-400 dark:hover:bg-gray-500 disabled:opacity-50">
                  取消
                </button>
              </div>
            </div>
          </div>
        )}

        {!sidebarCollapsed && importResult && (
          <div className="mt-2 p-2 bg-gray-800 rounded text-xs">
            <div className="text-green-400 mb-1">导入完成</div>
            <div>新增: {Object.entries(importResult.inserted).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
            <div>跳过: {Object.entries(importResult.skipped).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
            {Object.values(importResult.overwritten).some(v => v > 0) && (
              <div>覆盖: {Object.entries(importResult.overwritten).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
            )}
            {Object.values(importResult.kept_both).some(v => v > 0) && (
              <div>保留两份: {Object.entries(importResult.kept_both).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
            )}
            {(importResult.settings_imported ?? 0) > 0 && <div>设置恢复: {importResult.settings_imported} 项</div>}
            {(importResult.sessions_imported ?? 0) > 0 && <div>学习会话: 导入 {importResult.sessions_imported} 条</div>}
            {(importResult.sessions_skipped ?? 0) > 0 && <div className="text-gray-400">会话跳过: {importResult.sessions_skipped} 条（重复）</div>}
            {(importResult.sessions_invalid ?? 0) > 0 && <div className="text-yellow-400">会话无效: {importResult.sessions_invalid} 条（已跳过）</div>}
            {(importResult.sessions_warnings ?? []).length > 0 && (
              <div className="text-yellow-400">会话警告: {importResult.sessions_warnings!.slice(0, 3).join('; ')}{importResult.sessions_warnings!.length > 3 ? '...' : ''}</div>
            )}
            {(importResult.settings_warnings ?? []).length > 0 && (
              <div className="text-yellow-400">设置警告: {importResult.settings_warnings!.join('; ')}</div>
            )}
            <button onClick={() => setImportResult(null)} className="mt-1 text-gray-400 hover:text-gray-200 text-xs">关闭</button>
          </div>
        )}

        {/* ZIP Import preview/result */}
        {!sidebarCollapsed && zipPreview && (
          <div className="mt-2 p-2 bg-gray-800 rounded text-xs space-y-0.5">
            <div className="text-gray-400 mb-1 flex items-center gap-1">
              完整备份预览（{zipPreview.exported_at?.slice(0, 10)}）
              {zipPreview.zip_info && (
                <span className="text-blue-400">📦 {zipPreview.zip_info.file_count} 个文件</span>
              )}
              {zipPreviewLoading && <span className="text-blue-400 animate-pulse">刷新中...</span>}
            </div>
            <div>错题: {zipPreview.error_book_count} / 计划: {zipPreview.study_plans_count}</div>
            <div>真题: {zipPreview.exam_questions_count} / 答题: {zipPreview.exam_attempts_count}</div>
            <div>资料: {zipPreview.materials_count} / 问答: {zipPreview.chat_history_count}</div>
            <div>解析: {zipPreview.problems_count} / 设置: {zipPreview.app_settings_count ?? 0} / 会话: {zipPreview.study_sessions_count ?? 0}</div>
            {(zipPreview.settings_invalid ?? 0) > 0 && (
              <div className="text-yellow-400">{zipPreview.settings_invalid} 项设置数据无效，将跳过</div>
            )}
            {(zipPreview.sessions_invalid ?? 0) > 0 && (
              <div className="text-yellow-400">{zipPreview.sessions_invalid} 条会话数据无效，将跳过</div>
            )}
            {zipPreview.zip_info && (
              <div className="text-blue-300">
                文件: {zipPreview.zip_info.materials_with_files} 个有文件 / {zipPreview.zip_info.materials_without_files} 个无文件
              </div>
            )}

            {zipPreview.total_conflicts > 0 && (
              <div className="mt-1.5 pt-1.5 border-t border-gray-700 text-yellow-400">
                检测到 {zipPreview.total_conflicts} 条冲突数据
              </div>
            )}

            {zipPreview.total_conflicts > 0 && (
              <div className="mt-1 space-y-0.5">
                {Object.entries(zipPreview.modules).filter(([, s]) => s.conflict_count > 0).map(([mod, s]) => {
                  const action = s.would_skip > 0 ? `跳过${s.would_skip}` :
                    s.would_overwrite > 0 ? `覆盖${s.would_overwrite}` :
                    s.would_keep_both > 0 ? `保留${s.would_keep_both}` : '';
                  return (
                    <div key={mod} className="flex justify-between">
                      <span>{MODULE_LABELS[mod] || mod}:</span>
                      <span className="text-gray-400">新增{s.new_count} / 冲突{s.conflict_count} → {action}</span>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-2 pt-2 border-t border-gray-700">
              <div className="text-gray-400 mb-1">冲突策略：</div>
              <div className="flex flex-col gap-1">
                {(['skip', 'overwrite', 'keep_both'] as const).map(s => (
                  <label key={s} className={`flex items-center gap-1.5 ${zipPreviewLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
                    <input type="radio" name="zip-import-strategy" value={s}
                      checked={zipImportStrategy === s}
                      onChange={() => handleZipStrategyChange(s)}
                      disabled={zipPreviewLoading || zipImporting}
                      className="accent-blue-500" />
                    <span>{s === 'skip' ? '跳过（保留现有数据）' : s === 'overwrite' ? '覆盖（用导入数据替换）' : '保留两份（自动重命名）'}</span>
                  </label>
                ))}
              </div>
            </div>

            {zipImportStrategy === 'overwrite' && zipPreview.total_conflicts > 0 && (
              <div className="mt-1.5 p-1.5 bg-red-900/40 border border-red-700 rounded text-red-300">
                警告：覆盖策略将替换 {zipPreview.total_conflicts} 条现有数据并覆盖文件，此操作不可撤销！
              </div>
            )}

            <div className="flex gap-2 mt-2">
              <button onClick={handleZipImportClick} disabled={zipImporting || zipPreviewLoading} className="flex-1 px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
                {zipImporting ? '导入中...' : '确认导入'}
              </button>
              <button onClick={() => { setZipPreview(null); setZipFile(null); setZipImportError(''); }} disabled={zipImporting} className="flex-1 px-2 py-1 bg-gray-600 text-gray-300 rounded text-xs hover:bg-gray-500 disabled:opacity-50">
                取消
              </button>
            </div>
          </div>
        )}

        {/* ZIP overwrite confirmation modal */}
        {showZipOverwriteConfirm && zipPreview && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowZipOverwriteConfirm(false)}>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-4 max-w-xs mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
              <div className="text-red-600 dark:text-red-400 font-bold mb-2">确认覆盖导入？</div>
              <div className="text-sm text-gray-700 dark:text-gray-300 mb-3">
                将覆盖 {zipPreview.total_conflicts} 条现有数据并替换文件，此操作不可撤销。
              </div>
              <div className="flex gap-2">
                <button onClick={doZipImport} disabled={zipImporting} className="flex-1 px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50">
                  {zipImporting ? '导入中...' : '确认覆盖'}
                </button>
                <button onClick={() => setShowZipOverwriteConfirm(false)} disabled={zipImporting} className="flex-1 px-3 py-1.5 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded text-sm hover:bg-gray-400 dark:hover:bg-gray-500 disabled:opacity-50">
                  取消
                </button>
              </div>
            </div>
          </div>
        )}

        {!sidebarCollapsed && zipImportResult && (
          <div className="mt-2 p-2 bg-gray-800 rounded text-xs">
            <div className="text-green-400 mb-1">ZIP 导入完成（恢复 {zipImportResult.files_restored} 个文件）</div>
            <div>新增: {Object.entries(zipImportResult.inserted).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
            <div>跳过: {Object.entries(zipImportResult.skipped).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
            {Object.values(zipImportResult.overwritten).some(v => v > 0) && (
              <div>覆盖: {Object.entries(zipImportResult.overwritten).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
            )}
            {Object.values(zipImportResult.kept_both).some(v => v > 0) && (
              <div>保留两份: {Object.entries(zipImportResult.kept_both).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
            )}
            {(zipImportResult.settings_imported ?? 0) > 0 && <div>设置恢复: {zipImportResult.settings_imported} 项</div>}
            {(zipImportResult.sessions_imported ?? 0) > 0 && <div>学习会话: 导入 {zipImportResult.sessions_imported} 条</div>}
            {(zipImportResult.sessions_skipped ?? 0) > 0 && <div className="text-gray-400">会话跳过: {zipImportResult.sessions_skipped} 条（重复）</div>}
            {(zipImportResult.sessions_invalid ?? 0) > 0 && <div className="text-yellow-400">会话无效: {zipImportResult.sessions_invalid} 条（已跳过）</div>}
            {(zipImportResult.sessions_warnings ?? []).length > 0 && (
              <div className="text-yellow-400">会话警告: {zipImportResult.sessions_warnings!.slice(0, 3).join('; ')}{zipImportResult.sessions_warnings!.length > 3 ? '...' : ''}</div>
            )}
            {(zipImportResult.settings_warnings ?? []).length > 0 && (
              <div className="text-yellow-400">设置警告: {zipImportResult.settings_warnings!.join('; ')}</div>
            )}
            <button onClick={() => setZipImportResult(null)} className="mt-1 text-gray-400 hover:text-gray-200 text-xs">关闭</button>
          </div>
        )}
      </div>
    </aside>
    </>
  );
}
