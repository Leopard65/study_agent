import type { ExamQuestionItem, ExamAttemptItem } from '../api/client';
import LatexRenderer from './LatexRenderer';

interface ExamQuestionCardProps {
  question: ExamQuestionItem;
  expanded: boolean;
  busy: boolean;
  userAnswer: string;
  submitting: boolean;
  attempts: ExamAttemptItem[];
  addedToError: boolean;
  addingToError: boolean;
  onToggleExpand: () => void;
  onUserAnswerChange: (val: string) => void;
  onSubmit: () => void;
  onDelete: () => void;
  onAddToErrors: () => void;
}

export default function ExamQuestionCard({
  question: q, expanded, busy, userAnswer, submitting, attempts,
  addedToError, addingToError, onToggleExpand, onUserAnswerChange, onSubmit, onDelete, onAddToErrors,
}: ExamQuestionCardProps) {
  return (
    <div className={`bg-white dark:bg-gray-800 rounded-xl shadow ${busy ? 'opacity-50' : ''}`}>
      <div className="p-4 flex items-center justify-between cursor-pointer" onClick={onToggleExpand}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {q.subject && <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{q.subject}</span>}
            {q.year && <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">{q.year}</span>}
            {q.tags && q.tags.split(',').map(t => t.trim()).filter(Boolean).map(tag => (
              <span key={tag} className="px-2 py-0.5 bg-purple-100 text-purple-600 rounded text-xs">{tag}</span>
            ))}
          </div>
          <div className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate">{q.title}</div>
        </div>
        <div className="flex items-center gap-2 ml-3">
          <button
            onClick={e => { e.stopPropagation(); onDelete(); }}
            disabled={busy}
            className="text-red-400 hover:text-red-600 disabled:opacity-50 text-xs"
          >
            {busy ? '删除中...' : '删除'}
          </button>
          <span className="text-gray-400 text-xs">{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t">
          <div className="mt-3 mb-4">
            <div className="text-xs text-gray-400 mb-1">题目</div>
            <div className="prose prose-sm max-w-none bg-gray-50 dark:bg-gray-700 rounded p-3">
              <LatexRenderer content={q.question} />
            </div>
          </div>

          {q.answer && attempts.length === 0 && (
            <div className="mb-3">
              <div className="text-xs text-gray-400 mb-1">填写答案</div>
              <textarea
                className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                placeholder="输入你的答案..."
                value={userAnswer}
                onChange={e => onUserAnswerChange(e.target.value)}
              />
              <button
                onClick={onSubmit}
                disabled={submitting}
                className="mt-2 px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
              >
                {submitting ? '提交中...' : '提交答案'}
              </button>
            </div>
          )}

          {attempts.length > 0 && (
            <div className="mb-3">
              <div className="text-xs text-gray-400 mb-1">我的作答</div>
              {attempts.map(a => (
                <div key={a.id} className={`p-2 rounded text-sm mb-1 ${a.is_correct ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                  {a.user_answer || '（未填写答案）'}
                  {a.is_correct ? ' ✓ 正确' : ' ✗ 不正确'}
                </div>
              ))}
            </div>
          )}

          {q.answer && (
            <div className="mb-3">
              <div className="text-xs text-gray-400 mb-1">参考答案</div>
              <div className="prose prose-sm max-w-none bg-green-50 dark:bg-green-900/20 rounded p-3">
                <LatexRenderer content={q.answer} />
              </div>
            </div>
          )}

          {q.solution && (
            <div className="mb-3">
              <div className="text-xs text-gray-400 mb-1">解析过程</div>
              <div className="prose prose-sm max-w-none bg-blue-50 dark:bg-blue-900/20 rounded p-3">
                <LatexRenderer content={q.solution} />
              </div>
            </div>
          )}

          <div className="flex items-center gap-3 mt-3">
            <button
              onClick={onAddToErrors}
              disabled={addingToError || addedToError}
              className={`px-4 py-1.5 rounded-lg text-sm ${
                addedToError
                  ? 'bg-green-100 text-green-700 cursor-default'
                  : 'bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50'
              }`}
            >
              {addedToError ? '已加入错题本' : addingToError ? '保存中...' : '加入错题本'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
