import { useRef, useCallback } from 'react';

/**
 * 封装异步操作的防竞态 hook。
 * 组件卸载时自动递增序列号，丢弃过期的异步结果。
 */
export function useSafeAsync() {
  const seq = useRef(0);

  /**
   * 包装一个异步函数，返回可以在 effect 中安全调用的版本。
   * 如果组件卸载或新的 run 调用已发出，旧调用的结果会被丢弃。
   */
  const run = useCallback(<T>(fn: () => Promise<T>): Promise<T | undefined> => {
    const current = ++seq.current;
    return fn().then(
      (result) => (current === seq.current ? result : undefined),
      (err) => {
        if (current === seq.current) throw err;
        return undefined;
      },
    );
  }, []);

  /** 用于 effect cleanup：递增序列号使所有进行中的 run 失效 */
  const cancel = useCallback(() => {
    seq.current += 1;
  }, []);

  return { run, cancel };
}
