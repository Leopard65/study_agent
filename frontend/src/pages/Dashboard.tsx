import { useEffect, useState } from 'react';
import { getDashboard, listPlans } from '../api/client';

interface Stats {
  today_tasks: number;
  today_completed: number;
  total_materials: number;
  total_errors: number;
  unmastered_errors: number;
  streak_days: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [todayPlans, setTodayPlans] = useState<any[]>([]);

  useEffect(() => {
    getDashboard().then(setStats).catch(() => {});
    const today = new Date().toISOString().slice(0, 10);
    listPlans(today).then(setTodayPlans).catch(() => {});
  }, []);

  if (!stats) return <div className="p-6 text-gray-400">加载中...</div>;

  const cards = [
    { label: '今日任务', value: `${stats.today_completed}/${stats.today_tasks}`, color: 'bg-blue-500' },
    { label: '连续打卡', value: `${stats.streak_days} 天`, color: 'bg-green-500' },
    { label: '资料数量', value: stats.total_materials, color: 'bg-purple-500' },
    { label: '未掌握错题', value: stats.unmastered_errors, color: 'bg-red-500' },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">学习工作台</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {cards.map(c => (
          <div key={c.label} className="bg-white rounded-xl shadow p-5">
            <div className={`w-10 h-10 ${c.color} rounded-lg flex items-center justify-center text-white text-lg mb-3`}>
              {c.label[0]}
            </div>
            <div className="text-2xl font-bold text-gray-800">{c.value}</div>
            <div className="text-sm text-gray-500">{c.label}</div>
          </div>
        ))}
      </div>
      <div className="bg-white rounded-xl shadow p-5">
        <h2 className="text-lg font-semibold mb-4">今日计划</h2>
        {todayPlans.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无今日计划，去「学习计划」页面生成吧</p>
        ) : (
          <ul className="space-y-2">
            {todayPlans.map((p: any) => (
              <li key={p.id} className="flex items-center gap-3 text-sm">
                <span className={p.completed ? 'text-green-500' : 'text-gray-300'}>
                  {p.completed ? '✓' : '○'}
                </span>
                <span className="text-gray-500">{p.subject}</span>
                <span className={p.completed ? 'line-through text-gray-400' : 'text-gray-700'}>
                  {p.task}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
