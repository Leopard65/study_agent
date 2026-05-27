import { useRef, useState } from 'react';

interface Props {
  onUpload: (file: File) => Promise<void>;
  accept?: string;
  maxSizeMb?: number;
  onError?: (message: string) => void;
}

export default function FileUpload({ onUpload, accept = '.pdf,.docx,.doc,.txt,.md', maxSizeMb = 50, onError }: Props) {
  const ref = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > maxSizeMb * 1024 * 1024) {
      onError?.(`文件过大，最大支持 ${maxSizeMb}MB`);
      if (ref.current) ref.current.value = '';
      return;
    }

    setLoading(true);
    try {
      await onUpload(file);
    } finally {
      setLoading(false);
      if (ref.current) ref.current.value = '';
    }
  };

  return (
    <div>
      <input ref={ref} type="file" accept={accept} onChange={handleChange} className="hidden" />
      <button
        onClick={() => ref.current?.click()}
        disabled={loading}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
      >
        {loading ? '上传中...' : '上传资料'}
      </button>
    </div>
  );
}
