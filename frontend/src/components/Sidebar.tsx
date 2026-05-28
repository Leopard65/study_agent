import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { usePreferences } from '../hooks/usePreferences';
import { getHealth, exportJson, importPreview, importJson, getApiErrorMessage } from '../api/client';
import type { HealthStatus, ImportPreview, ImportResult } from '../api/client';

const links = [
  { to: '/', label: '学习工作台', icon: '📊' },
  { to: '/qa', label: 'AI 问答', icon: '💬' },
  { to: '/materials', label: '资料库', icon: '📚' },
  { to: '/problems', label: '题目解析', icon: '✏️' },
  { to: '/errors', label: '错题本', icon: '📝' },
  { to: '/plan', label: '学习计划', icon: '📅' },
  { to: '/exam', label: '真题练习', icon: '📋' },
  { to: '/search', label: '全局搜索', icon: '🔍' },
];

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
  const [exportError, setExportError] = useState('');

  // Import state
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [importData, setImportData] = useState<Record<string, unknown> | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => {}).finally(() => setChecking(false));
  }, []);

  const handleExport = async () => {
    setExporting(true);
    setExportError('');
    try {
      const blob = await exportJson();
      const date = new Date().toISOString().slice(0, 10);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `math_agent_backup_${date}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(getApiErrorMessage(err, '导出失败，请检查后端服务。'));
    } finally {
      setExporting(false);
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportError('');
    setPreview(null);
    setImportResult(null);
    setImporting(true);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      setImportData(data);
      const p = await importPreview(data);
      setPreview(p);
    } catch (err) {
      setImportError(getApiErrorMessage(err, '读取备份文件失败，请确认文件格式。'));
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  const handleImportConfirm = async () => {
    if (!importData) return;
    setImporting(true);
    setImportError('');
    try {
      const result = await importJson(importData);
      setImportResult(result);
      setPreview(null);
      setImportData(null);
    } catch (err) {
      setImportError(getApiErrorMessage(err, '导入失败，请检查后端服务。'));
    } finally {
      setImporting(false);
    }
  };

  let statusText = '服务正常';
  let statusColor = 'text-green-400';
  if (checking) {
    statusText = '检查中...';
    statusColor = 'text-gray-500';
  } else if (!health) {
    statusText = '服务异常';
    statusColor = 'text-red-400';
  } else if (health.status !== 'ok') {
    statusText = '服务异常';
    statusColor = 'text-red-400';
  } else if (!health.ai_configured) {
    statusText = '未配置 AI';
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
            <div className="text-gray-500 mt-2">MVP v0.2</div>
            <div className={`mt-1 ${statusColor}`}>{statusText}</div>
          </>
        )}
        {sidebarCollapsed && (
          <div className={`mt-1 text-center ${statusColor}`} title={statusText}>
            {checking ? '⏳' : health?.status === 'ok' ? '✅' : '❌'}
          </div>
        )}

        {/* Export */}
        <button
          onClick={handleExport}
          disabled={exporting}
          className={`mt-2 w-full px-3 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50 text-xs ${sidebarCollapsed ? 'px-1' : ''}`}
          title="导出数据备份"
        >
          {sidebarCollapsed ? '📤' : (exporting ? '导出中...' : '导出数据备份')}
        </button>
        {!sidebarCollapsed && exportError && <div className="mt-1 text-red-400">{exportError}</div>}

        {/* Import */}
        <label
          className={`mt-1.5 w-full px-3 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 text-xs text-center cursor-pointer block ${sidebarCollapsed ? 'px-1' : ''}`}
          title="导入备份"
        >
          {sidebarCollapsed ? '📥' : (importing ? '处理中...' : '导入备份')}
          <input type="file" accept=".json" className="hidden" onChange={handleFileSelect} disabled={importing} />
        </label>
        {!sidebarCollapsed && importError && <div className="mt-1 text-red-400">{importError}</div>}

        {/* Import preview/result - only in expanded mode */}
        {!sidebarCollapsed && preview && (
          <div className="mt-2 p-2 bg-gray-800 rounded text-xs space-y-0.5">
            <div className="text-gray-400 mb-1">备份预览（{preview.exported_at?.slice(0, 10)}）</div>
            <div>错题: {preview.error_book_count} / 计划: {preview.study_plans_count}</div>
            <div>真题: {preview.exam_questions_count} / 答题: {preview.exam_attempts_count}</div>
            <div>资料: {preview.materials_count} / 问答: {preview.chat_history_count}</div>
            <div>解析: {preview.problems_count}</div>
            <div className="flex gap-2 mt-2">
              <button onClick={handleImportConfirm} disabled={importing} className="flex-1 px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
                确认导入
              </button>
              <button onClick={() => { setPreview(null); setImportData(null); }} className="flex-1 px-2 py-1 bg-gray-600 text-gray-300 rounded text-xs hover:bg-gray-500">
                取消
              </button>
            </div>
          </div>
        )}
        {!sidebarCollapsed && importResult && (
          <div className="mt-2 p-2 bg-gray-800 rounded text-xs">
            <div className="text-green-400 mb-1">导入完成</div>
            <div>新增: {Object.entries(importResult.inserted).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
            <div>跳过: {Object.entries(importResult.skipped).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
            <button onClick={() => setImportResult(null)} className="mt-1 text-gray-400 hover:text-gray-200 text-xs">关闭</button>
          </div>
        )}
      </div>
    </aside>
    </>
  );
}
