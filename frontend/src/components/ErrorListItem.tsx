import type { ErrorBookItem } from '../api/client';
import LatexRenderer from './LatexRenderer';

interface ErrorListItemProps {
  item: ErrorBookItem;
  expanded: boolean;
  highlighted: boolean;
  busy: boolean;
  onToggleMastered: () => void;
  onToggleExpand: () => void;
  onDelete: () => void;
  deleting: boolean;
}

export default function ErrorListItem({
  item, expanded, highlighted, busy, onToggleMastered, onToggleExpand, onDelete, deleting,
}: ErrorListItemProps) {
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl shadow p-5 ${busy ? 'opacity-50' : ''} ${item.mastered && !busy ? 'opacity-60' : ''} ${highlighted ? 'ring-2 ring-blue-400' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          {item.subject && <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{item.subject}</span>}
          {item.chapter && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">{item.chapter}</span>}
          {item.knowledge_point && <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">{item.knowledge_point}</span>}
          {item.error_type && <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">{item.error_type}</span>}
          {item.tags && item.tags.split(',').map(t => t.trim()).filter(Boolean).map(tag => (
            <span key={tag} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-600 text-gray-500 dark:text-gray-300 rounded text-xs">{tag}</span>
          ))}
          <span className="px-2 py-0.5 bg-teal-100 text-teal-700 rounded text-xs">复习 {item.review_count} 次</span>
        </div>
        <div className="flex items-center gap-2">
          {item.next_review_date && <span className="text-xs text-gray-400">复习: {item.next_review_date}</span>}
          <button onClick={onToggleMastered} disabled={busy} className={`text-xs px-2 py-1 rounded ${item.mastered ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
            {item.mastered ? '已掌握' : '标记掌握'}
          </button>
          <button onClick={onToggleExpand} className="text-blue-400 hover:text-blue-600 text-xs">
            {expanded ? '收起' : '展开'}
          </button>
          <button onClick={onDelete} disabled={busy} className="text-red-400 hover:text-red-600 disabled:opacity-50 text-xs">{deleting ? '删除中...' : '删除'}</button>
        </div>
      </div>

      <div className="prose prose-sm max-w-none mb-2">
        <LatexRenderer content={item.question} />
      </div>

      {expanded && (
        <div className="mt-3 pt-3 border-t space-y-2 text-sm">
          {item.user_answer && <div><span className="font-medium text-red-600">错误答案：</span><div className="prose prose-sm max-w-none dark:text-gray-100"><LatexRenderer content={item.user_answer} /></div></div>}
          {item.correct_answer && <div><span className="font-medium text-green-600">正确答案：</span><div className="prose prose-sm max-w-none dark:text-gray-100"><LatexRenderer content={item.correct_answer} /></div></div>}
          {item.error_reason && <div><span className="font-medium text-gray-600">错误原因：</span>{item.error_reason}</div>}
          {item.correct_approach && <div><span className="font-medium text-blue-600">正确思路：</span>{item.correct_approach}</div>}
          {item.review_suggestion && <div><span className="font-medium text-purple-600">复习建议：</span>{item.review_suggestion}</div>}
        </div>
      )}
    </div>
  );
}
