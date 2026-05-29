import { useCallback, useEffect, useState } from 'react';
import {
  listExamQuestions, createExamQuestion, submitExamAttempt,
  addExamToErrors, deleteExamQuestion, generateExamQuestions,
  getApiErrorMessage,
} from '../api/client';
import type { ExamQuestionItem, ExamAttemptItem, ExamDraftItem } from '../api/client';
import LatexRenderer from '../components/LatexRenderer';
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

  const expandedQuestion = questions.find(q => q.id === expandedId);

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
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-5 mb-6">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">AI 生成练习题草稿</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <select className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" value={genForm.subject} onChange={e => setGenForm(f => ({ ...f, subject: e.target.value }))}>
              <option value="">选择科目（可选）</option>
              {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" placeholder="知识点/主题 *" value={genForm.topic} onChange={e => setGenForm(f => ({ ...f, topic: e.target.value }))} />
            <input className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" type="number" min={1} max={10} placeholder="数量" value={genForm.count} onChange={e => setGenForm(f => ({ ...f, count: e.target.value }))} />
            <select className="border rounded-lg px-3 py-2 text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100" value={genForm.difficulty} onChange={e => setGenForm(f => ({ ...f, difficulty: e.target.value }))}>
              <option value="">难度（可选）</option>
              <option value="easy">简单</option>
              <option value="medium">中等</option>
              <option value="hard">困难</option>
            </select>
          </div>
          <div className="flex items-center gap-3 mb-3">
            <label className="flex items-center gap-1.5 text-sm text-gray-600">
              <input type="checkbox" checked={genForm.use_materials} onChange={e => setGenForm(f => ({ ...f, use_materials: e.target.checked }))} />
              检索资料库辅助出题
            </label>
            <button onClick={handleGenerate} disabled={generating || !genForm.topic.trim()} className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 text-sm">
              {generating ? '生成中...' : '开始生成'}
            </button>
          </div>

          {genError && (
            <div className="mb-3 p-3 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-300">{genError}</div>
          )}
          {genRawResponse && (
            <details className="mb-3">
              <summary className="text-xs text-gray-400 cursor-pointer">查看 AI 原始返回</summary>
              <pre className="mt-1 p-3 bg-gray-50 dark:bg-gray-700 rounded text-xs text-gray-600 dark:text-gray-300 whitespace-pre-wrap break-all max-h-60 overflow-auto">{genRawResponse}</pre>
            </details>
          )}
        </div>
      )}

      {/* AI Generated drafts */}
      {drafts.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">生成草稿（{drafts.length} 题，点击展开预览）</h3>
          <div className="space-y-2">
            {drafts.map((d, idx) => (
              <div key={idx} className="bg-white dark:bg-gray-800 rounded-xl shadow">
                <div className="p-3 flex items-center justify-between cursor-pointer" onClick={() => setExpandedDraft(expandedDraft === idx ? null : idx)}>
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
                      onClick={e => { e.stopPropagation(); handleSaveDraft(idx); }}
                      disabled={savingDraft === idx}
                      className="px-3 py-1 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-xs"
                    >
                      {savingDraft === idx ? '保存中...' : '保存到题库'}
                    </button>
                    <span className="text-gray-400 text-xs">{expandedDraft === idx ? '▲' : '▼'}</span>
                  </div>
                </div>
                {expandedDraft === idx && (
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
      )}

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
          {questions.map(q => {
            const isExpanded = expandedId === q.id;
            const isBusy = deletingId === q.id;
            return (
              <div key={q.id} className={`bg-white dark:bg-gray-800 rounded-xl shadow ${isBusy ? 'opacity-50' : ''}`}>
                <div className="p-4 flex items-center justify-between cursor-pointer" onClick={() => { setExpandedId(isExpanded ? null : q.id); setUserAnswer(''); }}>
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
                      onClick={e => { e.stopPropagation(); handleDelete(q.id); }}
                      disabled={isBusy}
                      className="text-red-400 hover:text-red-600 disabled:opacity-50 text-xs"
                    >
                      {isBusy ? '删除中...' : '删除'}
                    </button>
                    <span className="text-gray-400 text-xs">{isExpanded ? '▲' : '▼'}</span>
                  </div>
                </div>

                {isExpanded && expandedQuestion && (
                  <div className="px-4 pb-4 border-t">
                    {/* Question content */}
                    <div className="mt-3 mb-4">
                      <div className="text-xs text-gray-400 mb-1">题目</div>
                      <div className="prose prose-sm max-w-none bg-gray-50 dark:bg-gray-700 rounded p-3">
                        <LatexRenderer content={expandedQuestion.question} />
                      </div>
                    </div>

                    {/* Answer area */}
                    {expandedQuestion.answer && !attempts[q.id]?.length && (
                      <div className="mb-3">
                        <div className="text-xs text-gray-400 mb-1">填写答案</div>
                        <textarea
                          className="w-full border rounded-lg px-3 py-2 text-sm h-20 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
                          placeholder="输入你的答案..."
                          value={userAnswer}
                          onChange={e => setUserAnswer(e.target.value)}
                        />
                        <button
                          onClick={() => handleSubmit(q.id)}
                          disabled={submitting}
                          className="mt-2 px-4 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
                        >
                          {submitting ? '提交中...' : '提交答案'}
                        </button>
                      </div>
                    )}

                    {/* Attempts history */}
                    {attempts[q.id]?.length > 0 && (
                      <div className="mb-3">
                        <div className="text-xs text-gray-400 mb-1">我的作答</div>
                        {attempts[q.id].map((a) => (
                          <div key={a.id} className={`p-2 rounded text-sm mb-1 ${a.is_correct ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                            {a.user_answer || '（未填写答案）'}
                            {a.is_correct ? ' ✓ 正确' : ' ✗ 不正确'}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Reference answer */}
                    {expandedQuestion.answer && (
                      <div className="mb-3">
                        <div className="text-xs text-gray-400 mb-1">参考答案</div>
                        <div className="prose prose-sm max-w-none bg-green-50 dark:bg-green-900/20 rounded p-3">
                          <LatexRenderer content={expandedQuestion.answer} />
                        </div>
                      </div>
                    )}

                    {/* Solution */}
                    {expandedQuestion.solution && (
                      <div className="mb-3">
                        <div className="text-xs text-gray-400 mb-1">解析过程</div>
                        <div className="prose prose-sm max-w-none bg-blue-50 dark:bg-blue-900/20 rounded p-3">
                          <LatexRenderer content={expandedQuestion.solution} />
                        </div>
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex items-center gap-3 mt-3">
                      <button
                        onClick={() => handleAddToErrors(q.id)}
                        disabled={addingToError === q.id || addedToError.has(q.id)}
                        className={`px-4 py-1.5 rounded-lg text-sm ${
                          addedToError.has(q.id)
                            ? 'bg-green-100 text-green-700 cursor-default'
                            : 'bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50'
                        }`}
                      >
                        {addedToError.has(q.id) ? '已加入错题本' : addingToError === q.id ? '保存中...' : '加入错题本'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
