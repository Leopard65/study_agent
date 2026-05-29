import type { ExamDraftItem } from '../api/client';
import LatexRenderer from './LatexRenderer';

interface ExamDraftListProps {
  drafts: ExamDraftItem[];
  expandedIdx: number | null;
  savingIdx: number | null;
  onToggleExpand: (idx: number) => void;
  onSave: (idx: number) => void;
}

export default function ExamDraftList({ drafts, expandedIdx, savingIdx, onToggleExpand, onSave }: ExamDraftListProps) {
  if (drafts.length === 0) return null;

  return (
    <div className="mb-6">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">生成草稿（{drafts.length} 题，点击展开预览）</h3>
      <div className="space-y-2">
        {drafts.map((d, idx) => (
          <div key={idx} className="bg-white dark:bg-gray-800 rounded-xl shadow">
            <div className="p-3 flex items-center justify-between cursor-pointer" onClick={() => onToggleExpand(idx)}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  {d.subject && <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{d.subject}</span>}
                  {d.year && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{d.year}</span>}
                  {d.tags && d.tags.split(',').map(t => t.trim()).filter(Boolean).map(tag => (
                    <span key={tag} className="px-2 py-0.5 bg-purple-100 text-purple-600 rounded text-xs">{tag}</span>
                  ))}
                </div>
                <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{d.title || '（无标题）'}</div>
              </div>
              <div className="flex items-center gap-2 ml-3">
                <button
                  onClick={e => { e.stopPropagation(); onSave(idx); }}
                  disabled={savingIdx === idx}
                  className="px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-xs"
                >
                  {savingIdx === idx ? '保存中...' : '保存到题库'}
                </button>
                <span className="text-gray-400 text-xs">{expandedIdx === idx ? '▲' : '▼'}</span>
              </div>
            </div>
            {expandedIdx === idx && (
              <div className="px-3 pb-3 border-t">
                <div className="mt-2 mb-2">
                  <div className="text-xs text-gray-400 mb-1">题目</div>
                  <div className="prose prose-sm max-w-none bg-gray-50 dark:bg-gray-700 rounded p-2">
                    <LatexRenderer content={d.question} />
                  </div>
                </div>
                {d.answer && (
                  <div className="mb-2">
                    <div className="text-xs text-gray-400 mb-1">参考答案</div>
                    <div className="prose prose-sm max-w-none bg-green-50 dark:bg-green-900/20 rounded p-2">
                      <LatexRenderer content={d.answer} />
                    </div>
                  </div>
                )}
                {d.solution && (
                  <div className="mb-2">
                    <div className="text-xs text-gray-400 mb-1">解析过程</div>
                    <div className="prose prose-sm max-w-none bg-blue-50 dark:bg-blue-900/20 rounded p-2">
                      <LatexRenderer content={d.solution} />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
