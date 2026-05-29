import { useCallback, useEffect, useState } from 'react';
import {
  listExamQuestions, createExamQuestion, submitExamAttempt,
  addExamToErrors, deleteExamQuestion, generateExamQuestions,
  getApiErrorMessage,
} from '../api/client';
import type { ExamQuestionItem, ExamAttemptItem, ExamDraftItem } from '../api/client';
import ExamGeneratePanel from '../components/ExamGeneratePanel';
import ExamDraftList from '../components/ExamDraftList';
import ExamQuestionCard from '../components/ExamQuestionCard';
import { SUBJECTS } from '../utils/constants';
import { useSafeAsync } from '../hooks/useSafeAsync';
import { useDeepLink } from '../hooks/useDeepLink';

export default function ExamPractice() {
  const { run, cancel } = useSafeAsync();
  const [questions, setQuestions] = useState<ExamQuestionItem[]>([]);
  const [filterSubject, setFilterSubject] = useState('');
  const [filterYear, setFilterYear] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Add form
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState({ title: '', subject: '', year: '', question: '', answer: '', solution: '', tags: '' });
  const [saving, setSaving] = useState(false);

  // Expanded question
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [userAnswer, setUserAnswer] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [attempts, setAttempts] = useState<Record<number, ExamAttemptItem[]>>({});

  // Add to error book
  const [addingToError, setAddingToError] = useState<number | null>(null);
  const [addedToError, setAddedToError] = useState<Set<number>>(new Set());
  const [addError, setAddError] = useState('');

  // Delete
  const [deletingId, setDeletingId] = useState<number | null>(null);

  // AI generate
  const [showGenerate, setShowGenerate] = useState(false);
  const [genForm, setGenForm] = useState({ subject: '', topic: '', count: '5', difficulty: '', use_materials: true });
  const [generating, setGenerating] = useState(false);
  const [drafts, setDrafts] = useState<ExamDraftItem[]>([]);
  const [genError, setGenError] = useState('');
  const [genRawResponse, setGenRawResponse] = useState('');
  const [expandedDraft, setExpandedDraft] = useState<number | null>(null);
  const [savingDraft, setSavingDraft] = useState<number | null>(null);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (filterSubject) params.subject = filterSubject;
    if (filterYear) params.year = filterYear;
    if (filterTag) params.tag = filterTag;
    run(() => listExamQuestions(Object.keys(params).length ? params : undefined))
      .then(items => {
        if (items !== undefined) {
          setError('');
          setQuestions(items);
          setLoading(false);
        }
      })
      .catch(err => {
        setError(getApiErrorMessage(err, '加载题目失败，请检查后端服务。'));
        setLoading(false);
      });
    return cancel;
  }, [filterSubject, filterYear, filterTag, run, cancel]);

  const loadQuestions = useCallback(async () => {
    const params: Record<string, string> = {};
    if (filterSubject) params.subject = filterSubject;
    if (filterYear) params.year = filterYear;
    if (filterTag) params.tag = filterTag;
    try {
      const items = await listExamQuestions(Object.keys(params).length ? params : undefined);
      setQuestions(items);
    } catch (err) {
      setError(getApiErrorMessage(err, '加载题目失败，请检查后端服务。'));
    }
  }, [filterSubject, filterYear, filterTag]);

  // Deep link: auto-expand exam question
  useDeepLink((id) => setExpandedId(id));

  const handleAdd = async () => {
    if (!addForm.title.trim() || !addForm.question.trim()) return;
    setSaving(true);
    setError('');
    try {
      await createExamQuestion(addForm);
      setAddForm({ title: '', subject: '', year: '', question: '', answer: '', solution: '', tags: '' });
      setShowAdd(false);
      await loadQuestions();
    } catch (err) {
      setError(getApiErrorMessage(err, '保存题目失败，请检查后端服务。'));
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async (questionId: number) => {
    setSubmitting(true);
    setError('');
    try {
      const attempt = await submitExamAttempt(questionId, { user_answer: userAnswer });
      setAttempts(prev => ({ ...prev, [questionId]: [...(prev[questionId] || []), attempt] }));
    } catch (err) {
      setError(getApiErrorMessage(err, '提交答案失败，请检查后端服务。'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddToErrors = async (questionId: number) => {
    setAddingToError(questionId);
    setAddError('');
    try {
      await addExamToErrors(questionId);
      setAddedToError(prev => new Set(prev).add(questionId));
    } catch (err) {
      const msg = getApiErrorMessage(err, '加入错题本失败，请检查后端服务。');
      if (msg.includes('已在错题本中')) {
        setAddedToError(prev => new Set(prev).add(questionId));
      }
      setAddError(msg);
    } finally {
      setAddingToError(null);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    setError('');
    try {
      await deleteExamQuestion(id);
      setQuestions(prev => prev.filter(q => q.id !== id));
      if (expandedId === id) setExpandedId(null);
    } catch (err) {
      setError(getApiErrorMessage(err, '删除题目失败，请检查后端服务。'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleGenerate = async () => {
    if (!genForm.topic.trim()) return;
    setGenerating(true);
    setGenError('');
    setGenRawResponse('');
    setDrafts([]);
    try {
      const resp = await generateExamQuestions({
        subject: genForm.subject || undefined,
        topic: genForm.topic.trim(),
        count: parseInt(genForm.count) || 5,
        difficulty: genForm.difficulty || undefined,
        use_materials: genForm.use_materials,
      });
      if (resp.parse_error) {
        setGenError(resp.parse_error);
        setGenRawResponse(resp.raw_response || '');
      } else {
        setDrafts(resp.drafts);
      }
    } catch (err) {
      setGenError(getApiErrorMessage(err, 'AI 生成失败，请检查后端服务。'));
    } finally {
      setGenerating(false);
    }
  };

  const handleSaveDraft = async (idx: number) => {
    const draft = drafts[idx];
    if (!draft) return;
    setSavingDraft(idx);
    setError('');
    try {
      await createExamQuestion({
        title: draft.title,
        subject: draft.subject,
        year: draft.year,
        question: draft.question,
        answer: draft.answer,
        solution: draft.solution,
        tags: draft.tags,
      });
      setDrafts(prev => prev.filter((_, i) => i !== idx));
      await loadQuestions();
    } catch (err) {
      setError(getApiErrorMessage(err, '保存草稿失败，请检查后端服务。'));
    } finally {
      setSavingDraft(null);
    }
  };

  const setForm = (key: keyof typeof addForm, val: string) => setAddForm(f => ({ ...f, [key]: val }));

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold dark:text-gray-100">真题练习</h1>
        <div className="flex gap-2">
          <button
            onClick={() => { setShowGenerate(!showGenerate); setShowAdd(false); }}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 text-sm"
          >
            {showGenerate ? '取消' : 'AI 生成练习题'}
          </button>
          <button
            onClick={() => { setShowAdd(!showAdd); setShowGenerate(false); }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
          >
            {showAdd ? '取消' : '手动添加'}
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select
          className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
          value={filterSubject}
          onChange={e => setFilterSubject(e.target.value)}
        >
          <option value="">全部科目</option>
          {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          className="border rounded-lg px-3 py-2 text-sm w-28 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
          placeholder="年份"
          value={filterYear}
          onChange={e => setFilterYear(e.target.value)}
        />
        <input
          className="border rounded-lg px-3 py-2 text-sm flex-1 min-w-[120px] dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
          placeholder="标签关键词"
          value={filterTag}
          onChange={e => setFilterTag(e.target.value)}
        />
        {(filterSubject || filterYear || filterTag) && (
          <button
            onClick={() => { setFilterSubject(''); setFilterYear(''); setFilterTag(''); }}
            className="px-3 py-2 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm"
          >
            清空筛选
          </button>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">{error}</div>
      )}
      {addError && (
        <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">{addError}</div>
      )}

      {/* AI Generate panel */}
      {showGenerate && (
        <ExamGeneratePanel
          form={genForm}
          onChange={setGenForm}
          onGenerate={handleGenerate}
          generating={generating}
          error={genError}
          rawResponse={genRawResponse}
        />
      )}

      {/* AI Generated drafts */}
      <ExamDraftList
        drafts={drafts}
        expandedIdx={expandedDraft}
        savingIdx={savingDraft}
        onToggleExpand={idx => setExpandedDraft(expandedDraft === idx ? null : idx)}
        onSave={handleSaveDraft}
      />

      {/* Add form */}
      {showAdd && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 mb-6">
          <div className="grid grid-cols-3 gap-3 mb-3">
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="题目标题" value={addForm.title} onChange={e => setForm('title', e.target.value)} />
            <select className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" value={addForm.subject} onChange={e => setForm('subject', e.target.value)}>
              <option value="">选择科目</option>
              {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="年份（如 2025）" value={addForm.year} onChange={e => setForm('year', e.target.value)} />
          </div>
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-24 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="题目内容（支持 LaTeX）" value={addForm.question} onChange={e => setForm('question', e.target.value)} />
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="参考答案（可选）" value={addForm.answer} onChange={e => setForm('answer', e.target.value)} />
          <textarea className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none mb-3 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="解析过程（可选）" value={addForm.solution} onChange={e => setForm('solution', e.target.value)} />
          <div className="flex items-center gap-3">
            <input className="flex-1 border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="标签（逗号分隔）" value={addForm.tags} onChange={e => setForm('tags', e.target.value)} />
            <button onClick={handleAdd} disabled={saving || !addForm.title.trim() || !addForm.question.trim()} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm">
              {saving ? '保存中...' : '保存'}
            </button>
          </div>
        </div>
      )}

      {/* Question list */}
      {loading ? (
        <p className="text-gray-400 text-sm">加载中...</p>
      ) : questions.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-10 text-center">
          <div className="text-4xl mb-3">📋</div>
          <p className="text-gray-500 dark:text-gray-400 text-sm">暂无题目，点击右上角添加</p>
        </div>
      ) : (
        <div className="space-y-3">
          {questions.map(q => (
            <ExamQuestionCard
              key={q.id}
              question={q}
              expanded={expandedId === q.id}
              busy={deletingId === q.id}
              userAnswer={userAnswer}
              submitting={submitting}
              attempts={attempts[q.id] || []}
              addedToError={addedToError.has(q.id)}
              addingToError={addingToError === q.id}
              onToggleExpand={() => { setExpandedId(expandedId === q.id ? null : q.id); setUserAnswer(''); }}
              onUserAnswerChange={setUserAnswer}
              onSubmit={() => handleSubmit(q.id)}
              onDelete={() => handleDelete(q.id)}
              onAddToErrors={() => handleAddToErrors(q.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
