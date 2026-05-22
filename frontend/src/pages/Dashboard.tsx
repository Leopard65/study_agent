import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { getDashboard, listPlans, updatePlan, listErrors, getApiErrorMessage } from '../api/client';
import type { DashboardStats, StudyPlanItem } from '../api/client';
import { formatLocalDate } from '../utils/date';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [todayPlans, setTodayPlans] = useState<StudyPlanItem[]>([]);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const [toggleError, setToggleError] = useState('');
  const [reviewCount, setReviewCount] = useState(0);

  const today = formatLocalDate();

  const refresh = useCallback(() => {
    getDashboard().then(setStats).catch(() => {});
    listPlans(today).then(setTodayPlans).catch(() => {});
    listErrors(false)
      .then(all => setReviewCount(all.filter(e => e.next_review_date && e.next_review_date <= today).length))
      .catch(() => setReviewCount(0));
  }, [today]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleToggle = async (id: number, completed: boolean) => {
    setUpdatingId(id);
    setToggleError('');
    try {
      await updatePlan(id, !completed);
      refresh();
    } catch (err) {
      setToggleError(getApiErrorMessage(err, '更新失败，请检查后端服务。'));
    } finally {
      setUpdatingId(null);
    }
  };

  if (!stats) return <div className="p-6 text-gray-400">加载中...</div>;

  const cards = [
    { label: '今日任务', value: `${stats.today_completed}/${stats.today_tasks}`, color: 'bg-blue-500' },
    { label: '连续打卡', value: `${stats.streak_days} 天`, color: 'bg-green-500' },
    { label: '今日复习', value: `${reviewCount} 题`, color: 'bg-orange-500' },
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
        {toggleError && (
          <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {toggleError}
          </div>
        )}
        {todayPlans.length === 0 ? (
          <p className="text-gray-400 text-sm">暂无今日计划，去「学习计划」页面生成吧</p>
        ) : (
          <ul className="space-y-2">
            {todayPlans.map((p) => (
              <li
                key={p.id}
                className={`flex items-center gap-3 text-sm cursor-pointer select-none ${updatingId === p.id ? 'opacity-50' : ''}`}
                onClick={() => updatingId !== p.id && handleToggle(p.id, p.completed)}
              >
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

      <div className="mt-4 bg-white rounded-xl shadow p-5">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">
            {reviewCount > 0
              ? `今天有 ${reviewCount} 道错题待复习`
              : '今天暂无需要复习的错题'}
          </span>
          {reviewCount > 0 && (
            <Link to="/errors?filter=review" className="text-sm text-blue-600 hover:text-blue-800">
              去复习 →
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
