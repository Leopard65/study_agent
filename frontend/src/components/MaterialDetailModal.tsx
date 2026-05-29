import type { MaterialDetail } from '../api/client';

const TYPE_LABEL: Record<string, string> = {
  '.pdf': 'PDF', '.docx': 'Word', '.doc': 'Word', '.txt': 'TXT', '.md': 'Markdown',
};

interface MaterialDetailModalProps {
  material: MaterialDetail;
  onClose: () => void;
}

export default function MaterialDetailModal({ material, onClose }: MaterialDetailModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-3xl w-full max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-800 dark:text-gray-100 truncate">{material.filename}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl ml-4">&times;</button>
        </div>
        <div className="px-6 py-4 overflow-y-auto flex-1">
          <div className="flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-400 mb-4">
            <span>文件类型：{TYPE_LABEL[material.file_type] || material.file_type}</span>
            <span>上传时间：{material.created_at ? new Date(material.created_at).toLocaleString() : '未知'}</span>
            {material.stored_filename && <span>存储文件名：{material.stored_filename}</span>}
            <span>文本长度：{material.content_length} 字符</span>
          </div>
          <div className="text-sm text-gray-700 dark:text-gray-300">
            {material.preview ? (
              <>
                <pre className="whitespace-pre-wrap bg-gray-50 rounded p-4 max-h-96 overflow-y-auto text-sm leading-relaxed">
                  {material.preview}
                </pre>
                {material.truncated && (
                  <p className="text-gray-400 text-xs mt-2">仅显示前 {material.preview.length} 字符预览</p>
                )}
              </>
            ) : (
              <p className="text-gray-400">暂无可预览文本，可能是文件解析失败或扫描版 PDF OCR 未识别到文字。</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
