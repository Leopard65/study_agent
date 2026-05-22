import { NavLink } from 'react-router-dom';

const links = [
  { to: '/', label: '学习工作台', icon: '📊' },
  { to: '/qa', label: 'AI 问答', icon: '💬' },
  { to: '/materials', label: '资料库', icon: '📚' },
  { to: '/problems', label: '题目解析', icon: '✏️' },
  { to: '/errors', label: '错题本', icon: '📝' },
  { to: '/plan', label: '学习计划', icon: '📅' },
  { to: '/exam', label: '真题练习', icon: '📋' },
];

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 text-gray-100 flex flex-col min-h-screen">
      <div className="px-4 py-5 text-lg font-bold border-b border-gray-700">
        考研学习助手
      </div>
      <nav className="flex-1 py-2">
        {links.map(l => (
          <NavLink
            key={l.to}
            to={l.to}
            end={l.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'
              }`
            }
          >
            <span>{l.icon}</span>
            <span>{l.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="px-4 py-3 text-xs text-gray-500 border-t border-gray-700">
        MVP v0.1
      </div>
    </aside>
  );
}
