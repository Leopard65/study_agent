import { SUBJECTS } from '../utils/constants';

interface GenForm {
  subject: string;
  topic: string;
  count: string;
  difficulty: string;
  use_materials: boolean;
}

interface ExamGeneratePanelProps {
  form: GenForm;
  onChange: (updater: (prev: GenForm) => GenForm) => void;
  onGenerate: () => void;
  generating: boolean;
  error: string;
  rawResponse: string;
}

export default function ExamGeneratePanel({ form, onChange, onGenerate, generating, error, rawResponse }: ExamGeneratePanelProps) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 mb-6">
      <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">AI 生成练习题草稿</h3>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <select className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" value={form.subject} onChange={e => onChange(f => ({ ...f, subject: e.target.value }))}>
          <option value="">选择科目（可选）</option>
          {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="知识点/主题 *" value={form.topic} onChange={e => onChange(f => ({ ...f, topic: e.target.value }))} />
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" type="number" min={1} max={10} placeholder="数量" value={form.count} onChange={e => onChange(f => ({ ...f, count: e.target.value }))} />
        <select className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" value={form.difficulty} onChange={e => onChange(f => ({ ...f, difficulty: e.target.value }))}>
          <option value="">难度（可选）</option>
          <option value="easy">简单</option>
          <option value="medium">中等</option>
          <option value="hard">困难</option>
        </select>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <label className="flex items-center gap-1.5 text-sm text-gray-600">
          <input type="checkbox" checked={form.use_materials} onChange={e => onChange(f => ({ ...f, use_materials: e.target.checked }))} />
          检索资料库辅助出题
        </label>
        <button onClick={onGenerate} disabled={generating || !form.topic.trim()} className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm">
          {generating ? '生成中...' : '开始生成'}
        </button>
      </div>

      {error && (
        <div className="mb-3 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">{error}</div>
      )}
      {rawResponse && (
        <details className="mb-3">
          <summary className="text-xs text-gray-400 cursor-pointer">查看 AI 原始返回</summary>
          <pre className="mt-1 p-3 bg-gray-50 dark:bg-gray-700 rounded text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-all max-h-60 overflow-auto">{rawResponse}</pre>
        </details>
      )}
    </div>
  );
}
