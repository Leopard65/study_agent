import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * 处理 ?open=<id>&q=<query> 深链接参数的 hook。
 * 读取 searchParams 中的 open 和 q 参数，调用 onOpen 回调，然后清除 open 参数（保留 q）。
 * 仅在组件挂载时执行一次。
 */
export function useDeepLink(onOpen: (id: number, query?: string) => void) {
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const openId = searchParams.get('open');
    if (openId) {
      const id = parseInt(openId, 10);
      if (!isNaN(id)) {
        const q = searchParams.get('q') || undefined;
        setTimeout(() => {
          onOpen(id, q);
          const next = new URLSearchParams(searchParams);
          next.delete('open');
          // 保留 q 参数以便刷新后仍能恢复
          setSearchParams(next, { replace: true });
        }, 0);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
