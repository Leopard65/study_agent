import { useEffect, useState } from 'react';
import { uploadMaterial, listMaterials, searchMaterials, deleteMaterial, getApiErrorMessage } from '../api/client';
import type { MaterialItem, MaterialSearchResult } from '../api/client';
import FileUpload from '../components/FileUpload';

export default function Materials() {
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MaterialSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = () => listMaterials().then(setMaterials).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleUpload = async (file: File) => {
    setError('');
    try {
      await uploadMaterial(file);
      load();
    } catch (err) {
      setError(getApiErrorMessage(err, '上传失败，请检查文件或后端服务。'));
    }
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setError('');
    setSearching(true);
    try {
      const r = await searchMaterials(query);
      setResults(r);
    } catch (err) {
      setResults([]);
      setError(getApiErrorMessage(err, '搜索失败，请检查后端服务。'));
    } finally {
      setSearching(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (deletingId === id) return;
    setError('');
    setDeletingId(id);
    try {
      await deleteMaterial(id);
      load();
      setResults(prev => prev.filter(r => r.material_id !== id));
    } catch (err) {
      setError(getApiErrorMessage(err, '删除失败，请检查后端服务。'));
    } finally {
      setDeletingId(null);
    }
  };

  const typeLabel: Record<string, string> = {
    '.pdf': 'PDF',
    '.docx': 'Word',
    '.doc': 'Word',
    '.txt': 'TXT',
    '.md': 'Markdown',
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">资料库</h1>
        <FileUpload onUpload={handleUpload} />
      </div>

      {/* Search */}
      <div className="flex gap-3 mb-6">
        <input
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
          placeholder="关键词检索资料内容..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
        />
        <button
          onClick={handleSearch}
          disabled={searching}
          className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
        >
          {searching ? '搜索中...' : '搜索'}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Search Results */}
      {results.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold mb-3">搜索结果</h2>
          <div className="space-y-2">
            {results.map(r => (
              <div key={r.material_id} className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
                <div className="font-medium text-gray-700">{r.filename}</div>
                <div className="text-gray-500 mt-1" dangerouslySetInnerHTML={{ __html: r.snippet.replace(/>>>/g, '<mark>').replace(/<<</g, '</mark>') }} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Material List */}
      <h2 className="text-lg font-semibold mb-3">已上传资料</h2>
      {materials.length === 0 ? (
        <p className="text-gray-400 text-sm">暂无资料，点击右上角上传</p>
      ) : (
        <div className="grid gap-3">
          {materials.map(m => (
            <div key={m.id} className={`bg-white rounded-lg shadow p-4 flex items-center justify-between ${deletingId === m.id ? 'opacity-50' : ''}`}>
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                  {typeLabel[m.file_type] || m.file_type}
                </span>
                <span className="text-sm text-gray-700">{m.filename}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">
                  {m.created_at ? new Date(m.created_at).toLocaleDateString() : ''}
                </span>
                <button onClick={() => handleDelete(m.id)} disabled={deletingId === m.id} className="text-red-400 hover:text-red-600 disabled:opacity-50 text-sm">
                  {deletingId === m.id ? '删除中...' : '删除'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
