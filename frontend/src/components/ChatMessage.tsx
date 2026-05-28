import LatexRenderer from './LatexRenderer';
import type { ChatSource } from '../api/client';

interface Props {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
}

export default function ChatMessage({ role, content, sources }: Props) {
  const isUser = role === 'user';
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
              {sources.map((s, i) => (
                <li key={i} className="text-xs text-gray-500 dark:text-gray-400">
                  <span className="font-medium text-gray-600 dark:text-gray-300">{s.filename}</span>
                  {s.snippet && (
                    <span className="ml-1 text-gray-400"> — {s.snippet}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
