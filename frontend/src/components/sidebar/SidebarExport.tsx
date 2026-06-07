interface SidebarExportProps {
  collapsed: boolean;
  exporting: boolean;
  exportingZip: boolean;
  exportError: string;
  anyImportBusy: boolean;
  onExport: () => void;
  onExportZip: () => void;
}

export default function SidebarExport({
  collapsed, exporting, exportingZip, exportError, anyImportBusy, onExport, onExportZip,
}: SidebarExportProps) {
  const disabled = exporting || exportingZip || anyImportBusy;

  return (
    <>
      <div className={`mt-2 flex gap-1 ${collapsed ? 'flex-col' : ''}`}>
        <button
          onClick={onExport}
          disabled={disabled}
          className={`flex-1 px-2 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 disabled:opacity-50 text-xs ${collapsed ? 'px-1' : ''}`}
          title="导出仅数据 (JSON)"
        >
          {collapsed ? '📄' : (exporting ? '...' : '数据 JSON')}
        </button>
        <button
          onClick={onExportZip}
          disabled={disabled}
          className={`flex-1 px-2 py-1.5 bg-blue-700 text-gray-300 rounded hover:bg-blue-600 disabled:opacity-50 text-xs ${collapsed ? 'px-1' : ''}`}
          title="导出完整备份 ZIP（含上传文件）"
        >
          {collapsed ? '📦' : (exportingZip ? '...' : '完整 ZIP')}
        </button>
      </div>
      {!collapsed && exportError && <div className="mt-1 text-red-400">{exportError}</div>}
    </>
  );
}
