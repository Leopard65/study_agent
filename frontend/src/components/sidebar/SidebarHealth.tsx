import { NavLink } from 'react-router-dom';
import type { HealthStatus } from '../../api/client';

interface SidebarHealthProps {
  collapsed: boolean;
  health: HealthStatus | null;
  checking: boolean;
}

export default function SidebarHealth({ collapsed, health, checking }: SidebarHealthProps) {
  let statusText = '运行正常';
  let statusColor = 'text-green-400';
  if (checking) {
    statusText = '检查中…';
    statusColor = 'text-gray-500';
  } else if (!health) {
    statusText = '后端未启动';
    statusColor = 'text-red-400';
  } else if (health.status !== 'ok') {
    statusText = '后端异常';
    statusColor = 'text-red-400';
  } else if (!health.ai_configured) {
    statusText = '需配置 API Key';
    statusColor = 'text-yellow-400';
  }

  if (collapsed) {
    return (
      <div className={`mt-1 text-center ${statusColor}`} title={statusText}>
        {checking ? '⏳' : !health || health.status !== 'ok' ? '❌' : !health.ai_configured ? '⚠️' : '✅'}
      </div>
    );
  }

  return (
    <>
      <div className="text-gray-500 mt-2">MVP v0.7</div>
      <div className={`mt-1 ${statusColor}`}>
        {!health?.ai_configured && health?.status === 'ok' ? (
          <NavLink to="/settings" className="hover:underline">{statusText}</NavLink>
        ) : statusText}
      </div>
    </>
  );
}
