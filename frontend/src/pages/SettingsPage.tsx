import { useEffect, useState } from 'react';
import { getAppSettings, updateAppSettings, getHealth, getApiErrorMessage } from '../api/client';
import type { AppSettings, HealthStatus, AppSettingsResult } from '../api/client';

const PRESET_MODELS: Record<string, string[]> = {
  'https://api.deepseek.com': ['deepseek-v4-flash', 'deepseek-chat', 'deepseek-reasoner'],
  'https://api.openai.com': ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  'http://localhost:11434/v1': ['qwen2.5:7b', 'llama3:8b', 'mistral:7b'],
};

// ── Status summary (runtime state from /api/health) ──

function StatusSummary({ settings, health }: { settings: AppSettings; health: HealthStatus | null }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-2">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">运行状态</h2>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <span className="text-gray-500">数据库</span>
        <span className={health?.database === 'ok' ? 'text-green-600' : 'text-red-500'}>
          {health?.database === 'ok' ? '正常' : health?.database || '未知'}
        </span>
        <span className="text-gray-500">AI 功能</span>
        <span className={settings.ai_configured ? 'text-green-600' : 'text-yellow-500'}>
          {settings.ai_configured ? '已配置' : '未配置 — 填入 API Key 即可启用'}
        </span>
        <span className="text-gray-500">当前模型</span>
        <span className="text-gray-900 dark:text-gray-100">{settings.openai_model}</span>
        <span className="text-gray-500">OCR 识别</span>
        <span className={health?.ocr_available ? 'text-green-600' : 'text-gray-400'}>
          {health?.ocr_available ? '可用' : '未安装 Tesseract（普通 PDF 不受影响）'}
        </span>
        <span className="text-gray-500">数据存储</span>
        <span className="text-gray-900 dark:text-gray-100">本地 SQLite + uploads/，不上传任何服务器</span>
      </div>
    </div>
  );
}

// ── API Key block ──

function ApiKeyBlock({
  settings, apiKey, setApiKey, setApiKeyTouched,
  confirmClear, setConfirmClear, saving, onClear,
}: {
  settings: AppSettings;
  apiKey: string;
  setApiKey: (v: string) => void;
  setApiKeyTouched: (v: boolean) => void;
  confirmClear: boolean;
  setConfirmClear: (v: boolean) => void;
  saving: boolean;
  onClear: () => void;
}) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-3">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">API Key</h2>
      <p className="text-xs text-gray-500">
        填入后解锁 AI 问答、题目解析、计划生成等功能。不填也能用错题本、复习、资料管理等核心功能。
      </p>
      <input
        type="password"
        value={apiKey}
        onChange={e => { setApiKey(e.target.value); setApiKeyTouched(true); }}
        placeholder={settings.ai_configured ? '已配置（留空则不修改）' : 'sk-...'}
        className="w-full px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      {settings.ai_configured && (
        <div className="flex items-center gap-2">
          <p className="text-xs text-green-600 flex-1">✓ 已配置 API Key，AI 功能可用</p>
          {!confirmClear ? (
            <button
              onClick={() => setConfirmClear(true)}
              className="text-xs text-red-500 hover:text-red-700 underline"
            >
              清空 API Key
            </button>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-red-500">确认清空？</span>
              <button
                onClick={onClear}
                disabled={saving}
                className="text-xs text-red-600 hover:text-red-800 underline disabled:opacity-50"
              >
                确认
              </button>
              <button
                onClick={() => setConfirmClear(false)}
                className="text-xs text-gray-500 hover:text-gray-700 underline"
              >
                取消
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Base URL + Model block ──

function ModelBlock({
  baseUrl, setBaseUrl, model, setModel,
}: {
  baseUrl: string;
  setBaseUrl: (v: string) => void;
  model: string;
  setModel: (v: string) => void;
}) {
  const currentModels = Object.entries(PRESET_MODELS).find(([url]) => baseUrl === url)?.[1];

  const handlePresetUrl = (url: string) => {
    setBaseUrl(url);
    const models = PRESET_MODELS[url];
    if (models && models.length > 0 && !models.includes(model)) {
      setModel(models[0]);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700 space-y-3">
      <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">API 地址与模型</h2>
      <p className="text-xs text-gray-500">支持任何 OpenAI-compatible API。选择预设或手动输入。</p>

      <div className="flex flex-wrap gap-1.5">
        {Object.keys(PRESET_MODELS).map(url => (
          <button
            key={url}
            onClick={() => handlePresetUrl(url)}
            className={`px-2.5 py-1 rounded text-xs transition-colors ${
              baseUrl === url
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
            }`}
          >
            {url.includes('deepseek') ? 'DeepSeek' : url.includes('openai') ? 'OpenAI' : 'Ollama (本地)'}
          </button>
        ))}
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">API 地址</label>
        <input
          type="text"
          value={baseUrl}
          onChange={e => setBaseUrl(e.target.value)}
          className="w-full px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-xs text-gray-500 mb-1">模型名称</label>
        {currentModels ? (
          <div className="flex flex-wrap gap-1.5 mb-1.5">
            {currentModels.map(m => (
              <button
                key={m}
                onClick={() => setModel(m)}
                className={`px-2 py-0.5 rounded text-xs ${
                  model === m
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        ) : null}
        <input
          type="text"
          value={model}
          onChange={e => setModel(e.target.value)}
          className="w-full px-3 py-2 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-900 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>
    </div>
  );
}

// ── Save + Result block ──

function SaveBlock({
  saving, error, result, onSave,
}: {
  saving: boolean;
  error: string;
  result: AppSettingsResult | null;
  onSave: () => void;
}) {
  return (
    <>
      <div className="flex items-center gap-3">
        <button
          onClick={onSave}
          disabled={saving}
          className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {saving ? '保存中…' : '保存设置'}
        </button>
        {error && <span className="text-sm text-red-500">{error}</span>}
      </div>

      {result && (
        <div className="p-3 rounded bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-sm text-green-700 dark:text-green-300">
          {result.note}
        </div>
      )}

      <p className="text-xs text-gray-400">
        设置保存到 backend/.env。当前请求已生效，其他进程需重启后端。
      </p>
    </>
  );
}

// ── Page ──

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<AppSettingsResult | null>(null);

  // Form state
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [model, setModel] = useState('');
  const [apiKeyTouched, setApiKeyTouched] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);

  useEffect(() => {
    Promise.all([getAppSettings(), getHealth()])
      .then(([s, h]) => {
        setSettings(s);
        setHealth(h);
        setBaseUrl(s.openai_base_url);
        setModel(s.openai_model);
      })
      .catch(() => setError('加载设置失败'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async (opts?: { clearKey?: boolean }) => {
    setSaving(true);
    setError('');
    setResult(null);
    try {
      const updates: Record<string, unknown> = {};
      if (opts?.clearKey) {
        updates.clear_api_key = true;
      } else if (apiKeyTouched && apiKey) {
        updates.openai_api_key = apiKey;
      }
      if (baseUrl !== settings?.openai_base_url) {
        updates.openai_base_url = baseUrl;
      }
      if (model !== settings?.openai_model) {
        updates.openai_model = model;
      }
      if (Object.keys(updates).length === 0) {
        setError('没有要保存的更改');
        return;
      }
      const res = await updateAppSettings(updates);
      setResult(res);
      setApiKey('');
      setApiKeyTouched(false);
      setConfirmClear(false);
      // Use confirmed values from response (not stale cache)
      setSettings(prev => prev ? {
        ...prev,
        ai_configured: res.ai_configured,
        openai_base_url: res.openai_base_url,
        openai_model: res.openai_model,
        ocr_enabled: res.ocr_enabled,
      } : prev);
    } catch (err) {
      setError(getApiErrorMessage(err, '保存失败'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">加载中…</div>;
  }

  if (!settings) {
    return <div className="flex items-center justify-center h-64 text-red-400">无法加载设置</div>;
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">设置</h1>

      <StatusSummary settings={settings} health={health} />

      <ApiKeyBlock
        settings={settings}
        apiKey={apiKey}
        setApiKey={setApiKey}
        setApiKeyTouched={setApiKeyTouched}
        confirmClear={confirmClear}
        setConfirmClear={setConfirmClear}
        saving={saving}
        onClear={() => handleSave({ clearKey: true })}
      />

      <ModelBlock
        baseUrl={baseUrl}
        setBaseUrl={setBaseUrl}
        model={model}
        setModel={setModel}
      />

      <SaveBlock
        saving={saving}
        error={error}
        result={result}
        onSave={() => handleSave()}
      />
    </div>
  );
}
