interface ErrorForm {
  subject: string;
  chapter: string;
  knowledge_point: string;
  question: string;
  user_answer: string;
  correct_answer: string;
  error_type: string;
  error_reason: string;
  correct_approach: string;
  review_suggestion: string;
  tags: string;
  next_review_date: string;
}

interface ErrorAddFormProps {
  form: ErrorForm;
  onChange: (key: keyof ErrorForm, val: string) => void;
  onSave: () => void;
  saving: boolean;
}

export default function ErrorAddForm({ form, onChange, onSave, saving }: ErrorAddFormProps) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 mb-6">
      <div className="grid grid-cols-3 gap-3 mb-3">
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="科目" value={form.subject} onChange={e => onChange('subject', e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="章节" value={form.chapter} onChange={e => onChange('chapter', e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="知识点" value={form.knowledge_point} onChange={e => onChange('knowledge_point', e.target.value)} />
      </div>
      <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="题目内容" value={form.question} onChange={e => onChange('question', e.target.value)} />
      <div className="grid grid-cols-2 gap-3 mb-3">
        <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="你的错误答案" value={form.user_answer} onChange={e => onChange('user_answer', e.target.value)} />
        <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="正确答案/解析" value={form.correct_answer} onChange={e => onChange('correct_answer', e.target.value)} />
      </div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="错误类型（如计算错误）" value={form.error_type} onChange={e => onChange('error_type', e.target.value)} />
        <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="标签（逗号分隔）" value={form.tags} onChange={e => onChange('tags', e.target.value)} />
        <input type="date" className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" title="下次复习时间" value={form.next_review_date} onChange={e => onChange('next_review_date', e.target.value)} />
      </div>
      <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-16 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="错误原因" value={form.error_reason} onChange={e => onChange('error_reason', e.target.value)} />
      <div className="grid grid-cols-2 gap-3 mb-3">
        <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="正确思路" value={form.correct_approach} onChange={e => onChange('correct_approach', e.target.value)} />
        <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="复习建议" value={form.review_suggestion} onChange={e => onChange('review_suggestion', e.target.value)} />
      </div>
      <button onClick={onSave} disabled={saving} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm">{saving ? '保存中...' : '保存'}</button>
    </div>
  );
}
