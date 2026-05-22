import { useState } from 'react';
import { solveProblem } from '../api/client';
import LatexRenderer from '../components/LatexRenderer';

export default function ProblemSolver() {
  const [question, setQuestion] = useState('');
  const [subject, setSubject] = useState('');
  const [solution, setSolution] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSolve = async () => {
    if (!question.trim()) return;
    setLoading(true);
    try {
      const res = await solveProblem(question, subject);
      setSolution(res.solution);
    } catch {
      setSolution('请求失败，请检查后端服务。');
    } finally {
      setLoading(false);
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
            onChange={e => setSubject(e.target.value)}
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
            onChange={e => setQuestion(e.target.value)}
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
          <h2 className="text-lg font-semibold mb-4">解析结果</h2>
          <div className="prose prose-sm max-w-none">
            <LatexRenderer content={solution} />
          </div>
        </div>
      )}
    </div>
  );
}
