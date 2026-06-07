import { useEffect, useRef, useState } from 'react';
import { usePreferences } from '../hooks/usePreferences';
import { getHealth, exportJson, exportZip, importPreview, importJson, importZipPreview, importZip, getApiErrorMessage } from '../api/client';
import type { HealthStatus, ImportPreview, ImportResult, ZipImportPreview, ZipImportResult } from '../api/client';
import { downloadBlob } from '../utils/constants';
import SidebarNav from './sidebar/SidebarNav';
import SidebarHealth from './sidebar/SidebarHealth';
import SidebarTheme from './sidebar/SidebarTheme';
import SidebarExport from './sidebar/SidebarExport';
import SidebarImport from './sidebar/SidebarImport';

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

  // ── Export handlers ──
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

  // ── JSON import handlers ──
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

  const anyImportBusy = importing || previewLoading || zipImporting || zipPreviewLoading;
  const w = sidebarCollapsed ? 'w-16' : 'w-56';
  const handleNavClick = () => onMobileClose?.();

  return (
    <>
    {mobileOpen && (
      <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={onMobileClose} />
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

      <SidebarNav collapsed={sidebarCollapsed} onNavClick={handleNavClick} />

      {/* Footer */}
      <div className={`py-3 text-xs border-t border-gray-700 ${sidebarCollapsed ? 'px-2' : 'px-4'}`}>
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

        <SidebarTheme collapsed={sidebarCollapsed} theme={theme} onSetTheme={setTheme} />
        <SidebarHealth collapsed={sidebarCollapsed} health={health} checking={checking} />

        <SidebarExport
          collapsed={sidebarCollapsed}
          exporting={exporting}
          exportingZip={exportingZip}
          exportError={exportError}
          anyImportBusy={anyImportBusy}
          onExport={handleExport}
          onExportZip={handleExportZip}
        />

        <SidebarImport
          collapsed={sidebarCollapsed}
          importing={importing}
          importError={importError}
          preview={preview}
          importResult={importResult}
          importStrategy={importStrategy}
          previewLoading={previewLoading}
          showOverwriteConfirm={showOverwriteConfirm}
          onFileSelect={handleFileSelect}
          onStrategyChange={handleStrategyChange}
          onImportClick={handleImportClick}
          onDoImport={doImport}
          onCancelImport={() => { setPreview(null); setImportData(null); setImportError(''); }}
          onCloseOverwriteConfirm={() => setShowOverwriteConfirm(false)}
          onCloseImportResult={() => setImportResult(null)}
          zipImporting={zipImporting}
          zipImportError={zipImportError}
          zipPreview={zipPreview}
          zipImportResult={zipImportResult}
          zipImportStrategy={zipImportStrategy}
          zipPreviewLoading={zipPreviewLoading}
          showZipOverwriteConfirm={showZipOverwriteConfirm}
          onZipFileSelect={handleZipFileSelect}
          onZipStrategyChange={handleZipStrategyChange}
          onZipImportClick={handleZipImportClick}
          onDoZipImport={doZipImport}
          onCancelZipImport={() => { setZipPreview(null); setZipFile(null); setZipImportError(''); }}
          onCloseZipOverwriteConfirm={() => setShowZipOverwriteConfirm(false)}
          onCloseZipImportResult={() => setZipImportResult(null)}
        />
      </div>
    </aside>
    </>
  );
}
