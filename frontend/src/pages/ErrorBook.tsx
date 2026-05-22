import { useEffect, useState } from 'react';
import { listErrors, createError, updateError, deleteError } from '../api/client';
import LatexRenderer from '../components/LatexRenderer';

interface ErrorItem {
  id: number;
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
  mastered: boolean;
  created_at: string;
}

const emptyForm = {
  subject: '', chapter: '', knowledge_point: '', question: '',
  user_answer: '', correct_answer: '', error_type: '', error_reason: '',
  correct_approach: '', review_suggestion: '', tags: '', next_review_date: '',
};

export default function ErrorBook() {
  const [errors, setErrors] = useState<ErrorItem[]>([]);
  const [filter, setFilter] = useState<'all' | 'unmastered' | 'mastered'>('all');
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const load = () => {
    const mastered = filter === 'all' ? undefined : filter === 'mastered';
    listErrors(mastered).then(setErrors).catch(() => {});
  };

  useEffect(() => { load(); }, [filter]);

  const handleAdd = async () => {
    if (!form.question.trim()) return;
    await createError(form);
    setForm(emptyForm);
    setShowAdd(false);
    load();
  };

  const toggleMastered = async (item: ErrorItem) => {
    await updateError(item.id, { mastered: !item.mastered });
    load();
  };

  const handleDelete = async (id: number) => {
    await deleteError(id);
    load();
  };

  const set = (key: string, val: string) => setForm(f => ({ ...f, [key]: val }));

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">错题本</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
        >
          {showAdd ? '取消' : '添加错题'}
        </button>
      </div>

      <div className="flex gap-2 mb-4">
        {(['all', 'unmastered', 'mastered'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm ${
              filter === f ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {{ all: '全部', unmastered: '未掌握', mastered: '已掌握' }[f]}
          </button>
        ))}
      </div>

      {showAdd && (
        <div className="bg-white rounded-xl shadow p-5 mb-6">
          <div className="grid grid-cols-3 gap-3 mb-3">
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="科目" value={form.subject} onChange={e => set('subject', e.target.value)} />
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="章节" value={form.chapter} onChange={e => set('chapter', e.target.value)} />
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="知识点" value={form.knowledge_point} onChange={e => set('knowledge_point', e.target.value)} />
          </div>
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none mb-3" placeholder="题目内容" value={form.question} onChange={e => set('question', e.target.value)} />
          <div className="grid grid-cols-2 gap-3 mb-3">
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none" placeholder="你的错误答案" value={form.user_answer} onChange={e => set('user_answer', e.target.value)} />
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none" placeholder="正确答案/解析" value={form.correct_answer} onChange={e => set('correct_answer', e.target.value)} />
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="错误类型（如计算错误）" value={form.error_type} onChange={e => set('error_type', e.target.value)} />
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="标签（逗号分隔）" value={form.tags} onChange={e => set('tags', e.target.value)} />
            <input type="date" className="border rounded-lg px-3 py-2 text-sm" title="下次复习时间" value={form.next_review_date} onChange={e => set('next_review_date', e.target.value)} />
          </div>
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-16 resize-none mb-3" placeholder="错误原因" value={form.error_reason} onChange={e => set('error_reason', e.target.value)} />
          <div className="grid grid-cols-2 gap-3 mb-3">
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none" placeholder="正确思路" value={form.correct_approach} onChange={e => set('correct_approach', e.target.value)} />
            <textarea className="border rounded-lg px-3 py-2 text-sm h-16 resize-none" placeholder="复习建议" value={form.review_suggestion} onChange={e => set('review_suggestion', e.target.value)} />
          </div>
          <button onClick={handleAdd} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm">保存</button>
        </div>
      )}

      {errors.length === 0 ? (
        <p className="text-gray-400 text-sm">暂无错题</p>
      ) : (
        <div className="space-y-3">
          {errors.map(item => (
            <div key={item.id} className={`bg-white rounded-xl shadow p-5 ${item.mastered ? 'opacity-60' : ''}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 flex-wrap">
                  {item.subject && <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{item.subject}</span>}
                  {item.chapter && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">{item.chapter}</span>}
                  {item.knowledge_point && <span className="px-2 py-0.5 bg-orange-100 text-orange-700 rounded text-xs">{item.knowledge_point}</span>}
                  {item.error_type && <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">{item.error_type}</span>}
                  {item.tags && item.tags.split(',').map(t => t.trim()).filter(Boolean).map(tag => (
                    <span key={tag} className="px-2 py-0.5 bg-gray-100 text-gray-500 rounded text-xs">{tag}</span>
                  ))}
                </div>
                <div className="flex items-center gap-2">
                  {item.next_review_date && <span className="text-xs text-gray-400">复习: {item.next_review_date}</span>}
                  <button onClick={() => toggleMastered(item)} className={`text-xs px-2 py-1 rounded ${item.mastered ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {item.mastered ? '已掌握' : '标记掌握'}
                  </button>
                  <button onClick={() => setExpandedId(expandedId === item.id ? null : item.id)} className="text-blue-400 hover:text-blue-600 text-xs">
                    {expandedId === item.id ? '收起' : '展开'}
                  </button>
                  <button onClick={() => handleDelete(item.id)} className="text-red-400 hover:text-red-600 text-xs">删除</button>
                </div>
              </div>

              <div className="prose prose-sm max-w-none mb-2">
                <LatexRenderer content={item.question} />
              </div>

              {expandedId === item.id && (
                <div className="mt-3 pt-3 border-t space-y-2 text-sm">
                  {item.user_answer && <div><span className="font-medium text-red-600">错误答案：</span><div className="prose prose-sm max-w-none"><LatexRenderer content={item.user_answer} /></div></div>}
                  {item.correct_answer && <div><span className="font-medium text-green-600">正确答案：</span><div className="prose prose-sm max-w-none"><LatexRenderer content={item.correct_answer} /></div></div>}
                  {item.error_reason && <div><span className="font-medium text-gray-600">错误原因：</span>{item.error_reason}</div>}
                  {item.correct_approach && <div><span className="font-medium text-blue-600">正确思路：</span>{item.correct_approach}</div>}
                  {item.review_suggestion && <div><span className="font-medium text-purple-600">复习建议：</span>{item.review_suggestion}</div>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
