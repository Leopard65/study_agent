import { useState } from 'react';
import { solveProblem, createError, getApiErrorMessage } from '../api/client';
import { formatLocalDate } from '../utils/date';
import LatexRenderer from '../components/LatexRenderer';

export default function ProblemSolver() {
  const [question, setQuestion] = useState('');
  const [subject, setSubject] = useState('');
  const [solution, setSolution] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');

  const handleSolve = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setSaved(false);
    setSaveError('');
    try {
      const res = await solveProblem(question, subject);
      setSolution(res.solution);
    } catch (err) {
      setSolution(getApiErrorMessage(err, '请求失败，请检查后端服务是否运行。'));
    } finally {
      setLoading(false);
    }
  };

  const handleSaveToErrorBook = async () => {
    setSaving(true);
    setSaveError('');
    try {
      await createError({
        question,
        subject: subject || undefined,
        correct_answer: solution,
        error_type: '待复盘',
        review_suggestion: '根据解析重新独立完成一遍，并记录卡住的步骤。',
        next_review_date: formatLocalDate(),
      });
      setSaved(true);
    } catch (err) {
      setSaveError(getApiErrorMessage(err, '保存失败，请检查后端服务是否运行。'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">题目解析</h1>
      <div className="bg-white rounded-xl shadow p-5 mb-6">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">科目（可选）</label>
          <select
            className="w-full border rounded-lg px-3 py-2 text-sm"
            value={subject}
            onChange={e => { setSubject(e.target.value); setSaved(false); setSaveError(''); }}
          >
            <option value="">自动判断</option>
            <option value="高等数学">高等数学</option>
            <option value="线性代数">线性代数</option>
            <option value="概率论">概率论</option>
            <option value="信号与系统">信号与系统</option>
          </select>
        </div>
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">题目内容</label>
          <textarea
            className="w-full border rounded-lg px-3 py-2 text-sm h-32 resize-none focus:outline-none focus:ring-2 focus:ring-blue-400"
            placeholder="输入题目，支持 LaTeX 格式，例如：求 $\int_0^1 x^2 dx$"
            value={question}
            onChange={e => { setQuestion(e.target.value); setSaved(false); setSaveError(''); }}
          />
        </div>
        <button
          onClick={handleSolve}
          disabled={loading}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {loading ? '解析中...' : '开始解析'}
        </button>
      </div>

      {solution && (
        <div className="bg-white rounded-xl shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">解析结果</h2>
            <button
              onClick={handleSaveToErrorBook}
              disabled={saving || saved}
              className={`px-4 py-1.5 rounded-lg text-sm ${
                saved
                  ? 'bg-green-100 text-green-700 cursor-default'
                  : 'bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50'
              }`}
            >
              {saved ? '已加入错题本' : saving ? '保存中...' : '加入错题本'}
            </button>
          </div>
          {saveError && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {saveError}
            </div>
          )}
          <div className="prose prose-sm max-w-none">
            <LatexRenderer content={solution} />
          </div>
        </div>
      )}
    </div>
  );
}
