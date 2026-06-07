const THEME_OPTIONS: { value: 'light' | 'dark' | 'system'; label: string; icon: string }[] = [
  { value: 'light', label: '浅色', icon: '☀️' },
  { value: 'dark', label: '深色', icon: '🌙' },
  { value: 'system', label: '跟随系统', icon: '💻' },
];

interface SidebarThemeProps {
  collapsed: boolean;
  theme: string;
  onSetTheme: (t: 'light' | 'dark' | 'system') => void;
}

export default function SidebarTheme({ collapsed, theme, onSetTheme }: SidebarThemeProps) {
  return (
    <div className={`mt-2 flex ${collapsed ? 'flex-col items-center gap-1' : 'gap-1'}`}>
      {THEME_OPTIONS.map(opt => (
        <button
          key={opt.value}
          onClick={() => onSetTheme(opt.value)}
          className={`px-1.5 py-1 rounded text-[10px] ${theme === opt.value ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700 hover:text-gray-200'}`}
          title={opt.label}
        >
          {collapsed ? opt.icon : opt.label}
        </button>
      ))}
    </div>
  );
}
