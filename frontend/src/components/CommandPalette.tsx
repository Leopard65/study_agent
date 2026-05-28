import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

interface Command {
  id: string;
  label: string;
  hint?: string;
  action: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onExport: () => void;
}

export default function CommandPalette({ open, onClose, onExport }: Props) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const commands: Command[] = [
    { id: 'dashboard', label: '打开学习工作台', hint: '/', action: () => { navigate('/'); onClose(); } },
    { id: 'search', label: '打开全局搜索', hint: '/search', action: () => { navigate('/search'); onClose(); } },
    { id: 'qa', label: '打开 AI 问答', hint: '/qa', action: () => { navigate('/qa'); onClose(); } },
    { id: 'materials', label: '打开资料库', hint: '/materials', action: () => { navigate('/materials'); onClose(); } },
    { id: 'problems', label: '打开题目解析', hint: '/problems', action: () => { navigate('/problems'); onClose(); } },
    { id: 'errors', label: '打开错题本', hint: '/errors', action: () => { navigate('/errors'); onClose(); } },
    { id: 'plan', label: '打开学习计划', hint: '/plan', action: () => { navigate('/plan'); onClose(); } },
    { id: 'exam', label: '打开真题练习', hint: '/exam', action: () => { navigate('/exam'); onClose(); } },
    { id: 'timer', label: '开始专注计时', hint: '跳转到工作台', action: () => { navigate('/?focus=timer'); onClose(); } },
    { id: 'export', label: '导出数据备份', hint: '下载 JSON 文件', action: () => { onExport(); onClose(); } },
  ];

  const filtered = query.trim()
    ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()) || c.id.includes(query.toLowerCase()))
    : commands;

  useEffect(() => {
    if (open) {
      setTimeout(() => {
        setQuery('');
        setSelected(0);
        inputRef.current?.focus();
      }, 0);
    }
  }, [open]);

  useEffect(() => {
    setTimeout(() => setSelected(0), 0);
  }, [query]);

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selected] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [selected]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelected(i => (i + 1) % filtered.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelected(i => (i - 1 + filtered.length) % filtered.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      filtered[selected]?.action();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] px-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="命令面板"
    >
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative bg-white dark:bg-gray-800 rounded-xl shadow-2xl w-full max-w-lg overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <input
          ref={inputRef}
          className="w-full px-4 py-3 text-sm border-b border-gray-200 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100 focus:outline-none"
          placeholder="输入命令或搜索页面..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          role="combobox"
          aria-expanded={true}
          aria-controls="command-list"
        />
        <div ref={listRef} id="command-list" className="max-h-64 overflow-y-auto" role="listbox">
          {filtered.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-gray-400">未找到匹配命令</div>
          ) : (
            filtered.map((cmd, i) => (
              <div
                key={cmd.id}
                className={`px-4 py-2.5 text-sm cursor-pointer flex items-center justify-between ${
                  i === selected ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300' : 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700'
                }`}
                onClick={cmd.action}
                onMouseEnter={() => setSelected(i)}
                role="option"
                aria-selected={i === selected}
              >
                <span>{cmd.label}</span>
                {cmd.hint && <span className="text-xs text-gray-400">{cmd.hint}</span>}
              </div>
            ))
          )}
        </div>
        <div className="px-4 py-2 border-t border-gray-100 text-[10px] text-gray-400 flex gap-4">
          <span>↑↓ 导航</span>
          <span>Enter 执行</span>
          <span>Esc 关闭</span>
        </div>
      </div>
    </div>
  );
}
