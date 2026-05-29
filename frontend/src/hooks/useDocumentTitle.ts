import { useEffect } from 'react';

/**
 * 当有待复习错题时，在浏览器标签页标题前显示数量，如 "(3) 考研学习助手"。
 * 无待复习时恢复默认标题。
 */
export function useReviewTitle(dueCount: number) {
  useEffect(() => {
    const base = '考研学习助手';
    if (dueCount > 0) {
      document.title = `(${dueCount}) ${base}`;
    } else {
      document.title = base;
    }
    return () => { document.title = base; };
  }, [dueCount]);
}
