import { useState, useRef, useEffect } from 'react';
import { chat } from '../api/client';
import ChatMessage from '../components/ChatMessage';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function QA() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

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
      const res = await chat(q);
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: '请求失败，请检查后端服务。' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="px-6 py-4 border-b bg-white">
        <h1 className="text-xl font-bold">AI 问答</h1>
        <p className="text-sm text-gray-400">支持数学公式 LaTeX 渲染</p>
      </div>
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-lg mb-2">👋 你好，我是考研学习助手</p>
            <p className="text-sm">可以问我数学、信号与系统等学科的问题</p>
          </div>
        )}
        {messages.map((m, i) => (
          <ChatMessage key={i} role={m.role} content={m.content} />
        ))}
        {loading && (
          <div className="flex justify-start mb-4">
            <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3 text-sm text-gray-400">
              思考中...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="px-6 py-4 border-t bg-white">
        <div className="flex gap-3">
          <input
            className="flex-1 border rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
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
  );
}
