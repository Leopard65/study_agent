import { useEffect, useState } from 'react';
import { listPlans, createPlan, updatePlan, deletePlan, generatePlan } from '../api/client';

interface PlanItem {
  id: number;
  date: string;
  subject: string;
  task: string;
  completed: boolean;
}

export default function StudyPlan() {
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [showAdd, setShowAdd] = useState(false);
  const [showGen, setShowGen] = useState(false);
  const [form, setForm] = useState({ date: '', subject: '', task: '' });
  const [genForm, setGenForm] = useState({ subjects: '高等数学,线性代数,概率论', daily_hours: 8, start_date: '', days: 7 });
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState('');

  const load = () => listPlans().then(setPlans).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleAdd = async () => {
    if (!form.date || !form.subject || !form.task) return;
    await createPlan(form);
    setForm({ date: '', subject: '', task: '' });
    setShowAdd(false);
    load();
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setGenError('');
    try {
      const res = await generatePlan({
        subjects: genForm.subjects.split(',').map(s => s.trim()),
        daily_hours: genForm.daily_hours,
        start_date: genForm.start_date,
        days: genForm.days,
      });
      if (res.parse_error) {
        setGenError(`解析失败：${res.parse_error}\n\nAI 原始返回：\n${res.raw_response || '(空)'}`);
      } else {
        setShowGen(false);
        load();
      }
    } catch {
      setGenError('请求失败，请检查后端服务是否运行。');
    } finally {
      setGenerating(false);
    }
  };

  const toggleDone = async (item: PlanItem) => {
    await updatePlan(item.id, !item.completed);
    load();
  };

  const handleDelete = async (id: number) => {
    await deletePlan(id);
    load();
  };

  const grouped = plans.reduce<Record<string, PlanItem[]>>((acc, p) => {
    (acc[p.date] ??= []).push(p);
    return acc;
  }, {});

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">学习计划</h1>
        <div className="flex gap-2">
          <button onClick={() => { setShowGen(!showGen); setShowAdd(false); setGenError(''); }} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm">
            {showGen ? '取消' : 'AI 生成计划'}
          </button>
          <button onClick={() => { setShowAdd(!showAdd); setShowGen(false); }} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm">
            {showAdd ? '取消' : '手动添加'}
          </button>
        </div>
      </div>

      {showGen && (
        <div className="bg-white rounded-xl shadow p-5 mb-6">
          <h3 className="font-semibold mb-3">AI 生成学习计划</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">科目（逗号分隔）</label>
              <input className="w-full border rounded-lg px-3 py-2 text-sm" value={genForm.subjects} onChange={e => setGenForm({ ...genForm, subjects: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">起始日期</label>
              <input type="date" className="w-full border rounded-lg px-3 py-2 text-sm" value={genForm.start_date} onChange={e => setGenForm({ ...genForm, start_date: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">每天学习时长（小时）</label>
              <input type="number" className="w-full border rounded-lg px-3 py-2 text-sm" value={genForm.daily_hours} onChange={e => setGenForm({ ...genForm, daily_hours: +e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">天数</label>
              <input type="number" className="w-full border rounded-lg px-3 py-2 text-sm" value={genForm.days} onChange={e => setGenForm({ ...genForm, days: +e.target.value })} />
            </div>
          </div>
          <button onClick={handleGenerate} disabled={generating} className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm">
            {generating ? '生成中...' : '开始生成'}
          </button>
          {genError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 whitespace-pre-wrap">
              {genError}
            </div>
          )}
        </div>
      )}

      {showAdd && (
        <div className="bg-white rounded-xl shadow p-5 mb-6">
          <div className="grid grid-cols-3 gap-4 mb-4">
            <input type="date" className="border rounded-lg px-3 py-2 text-sm" value={form.date} onChange={e => setForm({ ...form, date: e.target.value })} />
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="科目" value={form.subject} onChange={e => setForm({ ...form, subject: e.target.value })} />
            <input className="border rounded-lg px-3 py-2 text-sm" placeholder="任务内容" value={form.task} onChange={e => setForm({ ...form, task: e.target.value })} />
          </div>
          <button onClick={handleAdd} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm">添加</button>
        </div>
      )}

      {Object.keys(grouped).length === 0 ? (
        <p className="text-gray-400 text-sm">暂无计划，点击「AI 生成计划」快速创建</p>
      ) : (
        Object.entries(grouped)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([date, items]) => (
            <div key={date} className="mb-6">
              <h3 className="text-sm font-semibold text-gray-500 mb-2">{date}</h3>
              <div className="space-y-2">
                {items.map(item => (
                  <div key={item.id} className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => toggleDone(item)}
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-xs ${
                          item.completed ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300'
                        }`}
                      >
                        {item.completed ? '✓' : ''}
                      </button>
                      <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">{item.subject}</span>
                      <span className={`text-sm ${item.completed ? 'line-through text-gray-400' : 'text-gray-700'}`}>{item.task}</span>
                    </div>
                    <button onClick={() => handleDelete(item.id)} className="text-red-400 hover:text-red-600 text-xs">删除</button>
                  </div>
                ))}
              </div>
            </div>
          ))
      )}
    </div>
  );
}
