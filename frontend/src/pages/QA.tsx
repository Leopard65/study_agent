import { useState, useRef, useEffect, useCallback } from 'react';
import { chat, listConversations, deleteConversation, getApiErrorMessage } from '../api/client';
import type { ChatSource, ConversationItem } from '../api/client';
import ChatMessage from '../components/ChatMessage';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: ChatSource[];
}

export default function QA() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState('');
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [showSidebar, setShowSidebar] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(() => {
    listConversations().then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const res = await chat(q, undefined, conversationId || undefined);
      setConversationId(res.conversation_id);
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer, sources: res.sources }]);
      loadConversations();
    } catch (err) {
      const msg = getApiErrorMessage(err, '请求失败，请检查后端服务是否运行。');
      setMessages(prev => [...prev, { role: 'assistant', content: msg }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setConversationId('');
  };

  const handleSelectConversation = (convId: string) => {
    setConversationId(convId);
    // 从对话列表的标题推断消息（实际应从 history 加载）
    // 简单方案：清空并重新从 history 加载
    import('../api/client').then(({ getChatHistory }) => {
      getChatHistory(convId).then(history => {
        const loaded: Message[] = [];
        for (const h of history.reverse()) {
          loaded.push({ role: 'user', content: h.question });
          loaded.push({ role: 'assistant', content: h.answer });
        }
        setMessages(loaded);
      }).catch(() => {});
    });
    setShowSidebar(false);
  };

  const handleDeleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(convId);
      if (conversationId === convId) {
        handleNewChat();
      }
      loadConversations();
    } catch {
      // 忽略删除失败
    }
  };

  return (
    <div className="flex h-screen">
      {/* 对话列表侧边栏 */}
      {showSidebar && (
        <div className="w-64 border-r bg-white dark:bg-gray-800 dark:border-gray-700 flex flex-col shrink-0">
          <div className="p-3 border-b dark:border-gray-700 flex items-center justify-between">
            <span className="text-sm font-medium dark:text-gray-200">对话列表</span>
            <button onClick={() => setShowSidebar(false)} className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {conversations.length === 0 ? (
              <p className="p-3 text-xs text-gray-400">暂无历史对话</p>
            ) : (
              conversations.map(c => (
                <div
                  key={c.conversation_id}
                  onClick={() => handleSelectConversation(c.conversation_id)}
                  className={`px-3 py-2.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700 border-b dark:border-gray-700 ${conversationId === c.conversation_id ? 'bg-blue-50 dark:bg-blue-900/20' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-800 dark:text-gray-200 truncate flex-1">{c.title}</span>
                    <button
                      onClick={(e) => handleDeleteConversation(c.conversation_id, e)}
                      className="text-gray-300 hover:text-red-500 text-xs ml-1 shrink-0"
                    >删除</button>
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{c.message_count} 条消息</div>
                </div>
              ))
            )}
          </div>
          <div className="p-2 border-t dark:border-gray-700">
            <button
              onClick={handleNewChat}
              className="w-full px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs"
            >+ 新对话</button>
          </div>
        </div>
      )}

      {/* 主聊天区域 */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-6 py-3 border-b bg-white dark:bg-gray-800 dark:border-gray-700 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold dark:text-gray-100">AI 问答</h1>
            <p className="text-xs text-gray-400">
              {conversationId ? `对话中 · ${messages.length} 条消息` : '支持数学公式 LaTeX 渲染'}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-xs"
            >
              {showSidebar ? '隐藏历史' : '对话历史'}
            </button>
            <button
              onClick={handleNewChat}
              className="px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs"
            >新对话</button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-20">
              <p className="text-lg mb-2">👋 你好，我是考研学习助手</p>
              <p className="text-sm">可以问我数学、信号与系统等学科的问题</p>
              <p className="text-xs mt-1 text-gray-300">支持多轮对话，我会记住上下文</p>
            </div>
          )}
          {messages.map((m, i) => (
            <ChatMessage key={i} role={m.role} content={m.content} sources={m.sources} />
          ))}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl rounded-bl-md px-4 py-3 text-sm text-gray-400">
                思考中...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="px-6 py-4 border-t bg-white dark:bg-gray-800 dark:border-gray-700">
          <div className="flex gap-3">
            <input
              className="flex-1 border rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100"
              placeholder="输入问题，例如：求极限 lim(x→0) sin(x)/x"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            />
            <button
              onClick={send}
              disabled={loading}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 text-sm"
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
