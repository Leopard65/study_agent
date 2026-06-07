import type { ImportPreview, ImportResult, ZipImportPreview, ZipImportResult } from '../../api/client';

const MODULE_LABELS: Record<string, string> = {
  materials: '资料', error_book: '错题', study_plans: '计划',
  problems: '解析', chat_history: '问答', exam_questions: '真题',
  app_settings: '复习设置', study_sessions: '学习会话',
};

interface SidebarImportProps {
  collapsed: boolean;
  // JSON import
  importing: boolean;
  importError: string;
  preview: ImportPreview | null;
  importResult: ImportResult | null;
  importStrategy: 'skip' | 'overwrite' | 'keep_both';
  previewLoading: boolean;
  showOverwriteConfirm: boolean;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onStrategyChange: (s: 'skip' | 'overwrite' | 'keep_both') => void;
  onImportClick: () => void;
  onDoImport: () => void;
  onCancelImport: () => void;
  onCloseOverwriteConfirm: () => void;
  onCloseImportResult: () => void;
  // ZIP import
  zipImporting: boolean;
  zipImportError: string;
  zipPreview: ZipImportPreview | null;
  zipImportResult: ZipImportResult | null;
  zipImportStrategy: 'skip' | 'overwrite' | 'keep_both';
  zipPreviewLoading: boolean;
  showZipOverwriteConfirm: boolean;
  onZipFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onZipStrategyChange: (s: 'skip' | 'overwrite' | 'keep_both') => void;
  onZipImportClick: () => void;
  onDoZipImport: () => void;
  onCancelZipImport: () => void;
  onCloseZipOverwriteConfirm: () => void;
  onCloseZipImportResult: () => void;
}

function ImportResultBlock({ result, onClose }: { result: ImportResult; onClose: () => void }) {
  return (
    <div className="mt-2 p-2 bg-gray-800 rounded text-xs">
      <div className="text-green-400 mb-1">导入完成</div>
      <div>新增: {Object.entries(result.inserted).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
      <div>跳过: {Object.entries(result.skipped).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
      {Object.values(result.overwritten).some(v => v > 0) && (
        <div>覆盖: {Object.entries(result.overwritten).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
      )}
      {Object.values(result.kept_both).some(v => v > 0) && (
        <div>保留两份: {Object.entries(result.kept_both).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
      )}
      {(result.settings_imported ?? 0) > 0 && <div>设置恢复: {result.settings_imported} 项</div>}
      {(result.sessions_imported ?? 0) > 0 && <div>学习会话: 导入 {result.sessions_imported} 条</div>}
      {(result.sessions_skipped ?? 0) > 0 && <div className="text-gray-400">会话跳过: {result.sessions_skipped} 条（重复）</div>}
      {(result.sessions_invalid ?? 0) > 0 && <div className="text-yellow-400">会话无效: {result.sessions_invalid} 条（已跳过）</div>}
      {(result.sessions_warnings ?? []).length > 0 && (
        <div className="text-yellow-400">会话警告: {result.sessions_warnings!.slice(0, 3).join('; ')}{result.sessions_warnings!.length > 3 ? '...' : ''}</div>
      )}
      {(result.settings_warnings ?? []).length > 0 && (
        <div className="text-yellow-400">设置警告: {result.settings_warnings!.join('; ')}</div>
      )}
      <button onClick={onClose} className="mt-1 text-gray-400 hover:text-gray-200 text-xs">关闭</button>
    </div>
  );
}

function ZipResultBlock({ result, onClose }: { result: ZipImportResult; onClose: () => void }) {
  return (
    <div className="mt-2 p-2 bg-gray-800 rounded text-xs">
      <div className="text-green-400 mb-1">ZIP 导入完成（恢复 {result.files_restored} 个文件）</div>
      <div>新增: {Object.entries(result.inserted).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
      <div>跳过: {Object.entries(result.skipped).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ') || '无'}</div>
      {Object.values(result.overwritten).some(v => v > 0) && (
        <div>覆盖: {Object.entries(result.overwritten).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
      )}
      {Object.values(result.kept_both).some(v => v > 0) && (
        <div>保留两份: {Object.entries(result.kept_both).filter(([,v]) => v > 0).map(([k,v]) => `${k}=${v}`).join(', ')}</div>
      )}
      {(result.settings_imported ?? 0) > 0 && <div>设置恢复: {result.settings_imported} 项</div>}
      {(result.sessions_imported ?? 0) > 0 && <div>学习会话: 导入 {result.sessions_imported} 条</div>}
      {(result.sessions_skipped ?? 0) > 0 && <div className="text-gray-400">会话跳过: {result.sessions_skipped} 条（重复）</div>}
      {(result.sessions_invalid ?? 0) > 0 && <div className="text-yellow-400">会话无效: {result.sessions_invalid} 条（已跳过）</div>}
      {(result.sessions_warnings ?? []).length > 0 && (
        <div className="text-yellow-400">会话警告: {result.sessions_warnings!.slice(0, 3).join('; ')}{result.sessions_warnings!.length > 3 ? '...' : ''}</div>
      )}
      {(result.settings_warnings ?? []).length > 0 && (
        <div className="text-yellow-400">设置警告: {result.settings_warnings!.join('; ')}</div>
      )}
      <button onClick={onClose} className="mt-1 text-gray-400 hover:text-gray-200 text-xs">关闭</button>
    </div>
  );
}

function PreviewBlock({
  preview, strategy, loading, isZip,
  onStrategyChange, onImportClick, onCancel, importing,
}: {
  preview: ImportPreview | ZipImportPreview;
  strategy: 'skip' | 'overwrite' | 'keep_both';
  loading: boolean;
  isZip: boolean;
  onStrategyChange: (s: 'skip' | 'overwrite' | 'keep_both') => void;
  onImportClick: () => void;
  onCancel: () => void;
  importing: boolean;
}) {
  const testidPrefix = isZip ? 'zip-import' : 'json-import';
  const title = isZip ? '完整备份预览' : '备份预览';
  const zipInfo = isZip ? (preview as ZipImportPreview).zip_info : null;

  return (
    <div data-testid={`${testidPrefix}-preview`} className="mt-2 p-2 bg-gray-800 rounded text-xs space-y-0.5">
      <div className="text-gray-400 mb-1 flex items-center gap-1">
        {title}（{preview.exported_at?.slice(0, 10)}）
        {zipInfo && (
          <span className="text-blue-400">📦 {zipInfo.file_count} 个文件</span>
        )}
        {loading && <span className="text-blue-400 animate-pulse">刷新中...</span>}
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
      {zipInfo && (
        <div className="text-blue-300">
          文件: {zipInfo.materials_with_files} 个有文件 / {zipInfo.materials_without_files} 个无文件
        </div>
      )}

      {preview.total_conflicts > 0 && (
        <div className="mt-1.5 pt-1.5 border-t border-gray-700 text-yellow-400">
          检测到 {preview.total_conflicts} 条冲突数据
        </div>
      )}

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

      {Object.keys(preview.conflict_samples).length > 0 && (
        <div className="mt-1 text-gray-500">
          {Object.entries(preview.conflict_samples).map(([mod, samples]) => (
            <div key={mod}>
              {MODULE_LABELS[mod]}冲突项: {samples.map(s => `"${s}"`).join(', ')}
            </div>
          ))}
        </div>
      )}

      <div className="mt-2 pt-2 border-t border-gray-700">
        <div className="text-gray-400 mb-1">冲突策略：</div>
        <div className="flex flex-col gap-1">
          {(['skip', 'overwrite', 'keep_both'] as const).map(s => (
            <label key={s} className={`flex items-center gap-1.5 ${loading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
              <input type="radio" name={`${testidPrefix}-strategy`} value={s}
                checked={strategy === s}
                onChange={() => onStrategyChange(s)}
                disabled={loading || importing}
                className="accent-blue-500" />
              <span>{s === 'skip' ? '跳过（保留现有数据）' : s === 'overwrite' ? '覆盖（用导入数据替换）' : '保留两份（自动重命名）'}</span>
            </label>
          ))}
        </div>
      </div>

      {strategy === 'overwrite' && preview.total_conflicts > 0 && (
        <div className="mt-1.5 p-1.5 bg-red-900/40 border border-red-700 rounded text-red-300">
          警告：覆盖策略将替换 {preview.total_conflicts} 条现有数据{isZip ? '并覆盖文件' : ''}，此操作不可撤销！
        </div>
      )}

      <div className="flex gap-2 mt-2">
        <button onClick={onImportClick} disabled={importing || loading} className="flex-1 px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700 disabled:opacity-50">
          {importing ? '导入中...' : '确认导入'}
        </button>
        <button data-testid={`${testidPrefix}-cancel`} onClick={onCancel} disabled={importing} className="flex-1 px-2 py-1 bg-gray-600 text-gray-300 rounded text-xs hover:bg-gray-500 disabled:opacity-50">
          取消
        </button>
      </div>
    </div>
  );
}

function OverwriteConfirmModal({
  conflictCount, isZip, importing, onConfirm, onCancel,
}: {
  conflictCount: number;
  isZip: boolean;
  importing: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onCancel}>
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 max-w-xs mx-4 shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="text-red-600 dark:text-red-400 font-bold mb-2">确认覆盖导入？</div>
        <div className="text-sm text-gray-700 dark:text-gray-300 mb-3">
          将覆盖 {conflictCount} 条现有数据{isZip ? '并替换文件' : ''}，此操作不可撤销。
        </div>
        <div className="flex gap-2">
          <button onClick={onConfirm} disabled={importing} className="flex-1 px-3 py-1.5 bg-red-600 text-white rounded text-sm hover:bg-red-700 disabled:opacity-50">
            {importing ? '导入中...' : '确认覆盖'}
          </button>
          <button onClick={onCancel} disabled={importing} className="flex-1 px-3 py-1.5 bg-gray-300 dark:bg-gray-600 text-gray-700 dark:text-gray-200 rounded text-sm hover:bg-gray-400 dark:hover:bg-gray-500 disabled:opacity-50">
            取消
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SidebarImport(props: SidebarImportProps) {
  const { collapsed } = props;
  const anyBusy = props.importing || props.previewLoading || props.zipImporting || props.zipPreviewLoading;

  return (
    <>
      {/* Import buttons */}
      <div className={`mt-1.5 flex gap-1 ${collapsed ? 'flex-col' : ''}`}>
        <label
          className={`flex-1 px-2 py-1.5 bg-gray-700 text-gray-300 rounded hover:bg-gray-600 text-xs text-center cursor-pointer block ${collapsed ? 'px-1' : ''} ${anyBusy ? 'opacity-50 pointer-events-none' : ''}`}
          title="导入数据 JSON"
        >
          {collapsed ? '📄' : (props.importing ? '...' : props.previewLoading ? '...' : '导入 JSON')}
          <input type="file" accept=".json" className="hidden" onChange={props.onFileSelect} disabled={anyBusy} />
        </label>
        <label
          className={`flex-1 px-2 py-1.5 bg-blue-700 text-gray-300 rounded hover:bg-blue-600 text-xs text-center cursor-pointer block ${collapsed ? 'px-1' : ''} ${anyBusy ? 'opacity-50 pointer-events-none' : ''}`}
          title="导入完整备份 ZIP"
        >
          {collapsed ? '📦' : (props.zipImporting ? '...' : props.zipPreviewLoading ? '...' : '导入 ZIP')}
          <input type="file" accept=".zip" className="hidden" onChange={props.onZipFileSelect} disabled={anyBusy} />
        </label>
      </div>
      {!collapsed && props.importError && <div className="mt-1 text-red-400">{props.importError}</div>}
      {!collapsed && props.zipImportError && <div className="mt-1 text-red-400">{props.zipImportError}</div>}

      {/* JSON preview */}
      {!collapsed && props.preview && (
        <PreviewBlock
          preview={props.preview}
          strategy={props.importStrategy}
          loading={props.previewLoading}
          isZip={false}
          onStrategyChange={props.onStrategyChange}
          onImportClick={props.onImportClick}
          onCancel={props.onCancelImport}
          importing={props.importing}
        />
      )}

      {/* JSON overwrite confirm */}
      {props.showOverwriteConfirm && props.preview && (
        <OverwriteConfirmModal
          conflictCount={props.preview.total_conflicts}
          isZip={false}
          importing={props.importing}
          onConfirm={props.onDoImport}
          onCancel={props.onCloseOverwriteConfirm}
        />
      )}

      {/* JSON result */}
      {!collapsed && props.importResult && (
        <ImportResultBlock result={props.importResult} onClose={props.onCloseImportResult} />
      )}

      {/* ZIP preview */}
      {!collapsed && props.zipPreview && (
        <PreviewBlock
          preview={props.zipPreview}
          strategy={props.zipImportStrategy}
          loading={props.zipPreviewLoading}
          isZip={true}
          onStrategyChange={props.onZipStrategyChange}
          onImportClick={props.onZipImportClick}
          onCancel={props.onCancelZipImport}
          importing={props.zipImporting}
        />
      )}

      {/* ZIP overwrite confirm */}
      {props.showZipOverwriteConfirm && props.zipPreview && (
        <OverwriteConfirmModal
          conflictCount={props.zipPreview.total_conflicts}
          isZip={true}
          importing={props.zipImporting}
          onConfirm={props.onDoZipImport}
          onCancel={props.onCloseZipOverwriteConfirm}
        />
      )}

      {/* ZIP result */}
      {!collapsed && props.zipImportResult && (
        <ZipResultBlock result={props.zipImportResult} onClose={props.onCloseZipImportResult} />
      )}
    </>
  );
}
