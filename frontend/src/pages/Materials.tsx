import { useEffect, useState } from 'react';
import { uploadMaterial, listMaterials, searchMaterials, deleteMaterial } from '../api/client';
import FileUpload from '../components/FileUpload';

interface Material {
  id: number;
  filename: string;
  file_type: string;
  created_at: string;
}

interface SearchResult {
  material_id: number;
  filename: string;
  snippet: string;
}

export default function Materials() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const load = () => listMaterials().then(setMaterials).catch(() => {});
  useEffect(() => { load(); }, []);

  const handleUpload = async (file: File) => {
    await uploadMaterial(file);
    load();
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await searchMaterials(query);
      setResults(r);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleDelete = async (id: number) => {
    await deleteMaterial(id);
    load();
    setResults(prev => prev.filter(r => r.material_id !== id));
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
            <div key={m.id} className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="px-2 py-1 bg-gray-100 rounded text-xs font-mono">
                  {typeLabel[m.file_type] || m.file_type}
                </span>
                <span className="text-sm text-gray-700">{m.filename}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">
                  {new Date(m.created_at).toLocaleDateString()}
                </span>
                <button onClick={() => handleDelete(m.id)} className="text-red-400 hover:text-red-600 text-sm">
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
