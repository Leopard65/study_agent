import { useNavigate } from 'react-router-dom';
import LatexRenderer from './LatexRenderer';
import type { ChatSource } from '../api/client';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
}

/** 从 snippet 中提取前 20 个字符作为搜索关键词（去掉高亮标记和省略号） */
function snippetToQuery(snippet: string): string {
  const cleaned = snippet.replace(/\.{3}/g, '').replace(/>>>/g, '').replace(/<<</g, '').trim();
  return cleaned.slice(0, 20);
}

export default function ChatMessage({ role, content, sources }: Props) {
  const isUser = role === 'user';
  const navigate = useNavigate();
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white rounded-br-md'
            : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-100 rounded-bl-md'
        }`}
      >
        {isUser ? (
          <span className="whitespace-pre-wrap">{content}</span>
        ) : (
          <div className="prose prose-sm max-w-none dark:text-gray-100">
            <LatexRenderer content={content} />
          </div>
        )}
        {!isUser && sources && sources.length > 0 && (
          <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
            <div className="text-xs text-gray-400 mb-1">参考资料</div>
            <ul className="space-y-1">
              {sources.map((s, i) => {
                const q = s.snippet ? snippetToQuery(s.snippet) : '';
                const href = `/materials?open=${s.material_id}${q ? `&q=${encodeURIComponent(q)}` : ''}`;
                return (
                  <li key={i}>
                    <button
                      onClick={() => navigate(href)}
                      className="text-left text-xs text-blue-500 dark:text-blue-400 hover:underline cursor-pointer"
                    >
                      <span className="font-medium">{s.filename}</span>
                      {s.snippet && (
                        <span className="ml-1 text-gray-400 dark:text-gray-500"> — {s.snippet}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
