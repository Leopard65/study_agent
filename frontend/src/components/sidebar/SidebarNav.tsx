import { NavLink } from 'react-router-dom';

const links = [
  { to: '/', label: '学习工作台', icon: '📊' },
  { to: '/qa', label: 'AI 问答', icon: '💬' },
  { to: '/materials', label: '资料库', icon: '📚' },
  { to: '/problems', label: '题目解析', icon: '✏️' },
  { to: '/errors', label: '错题本', icon: '📝' },
  { to: '/plan', label: '学习计划', icon: '📅' },
  { to: '/exam', label: '真题练习', icon: '📋' },
  { to: '/review', label: '今日复习', icon: '🔄' },
  { to: '/search', label: '全局搜索', icon: '🔍' },
  { to: '/maintenance', label: '数据维护', icon: '🛠️' },
  { to: '/settings', label: '设置', icon: '⚙️' },
];

interface SidebarNavProps {
  collapsed: boolean;
  onNavClick: () => void;
}

export default function SidebarNav({ collapsed, onNavClick }: SidebarNavProps) {
  return (
    <nav className="flex-1 py-2">
      {links.map(l => (
        <NavLink
          key={l.to}
          to={l.to}
          end={l.to === '/'}
          title={collapsed ? l.label : undefined}
          onClick={onNavClick}
          className={({ isActive }) =>
            `flex items-center ${collapsed ? 'justify-center px-2' : 'gap-3 px-4'} py-2.5 text-sm transition-colors ${
              isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'
            }`
          }
        >
          <span className="text-base">{l.icon}</span>
          {!collapsed && <span>{l.label}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
