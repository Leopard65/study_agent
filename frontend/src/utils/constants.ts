export const SUBJECTS = ['高等数学', '线性代数', '概率论', '信号与系统', '其他'] as const;

export type Subject = (typeof SUBJECTS)[number];

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
