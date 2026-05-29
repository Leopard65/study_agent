import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';

/**
 * 处理 ?open=<id> 深链接参数的 hook。
 * 读取 searchParams 中的 open 参数，调用 onOpen 回调，然后清除参数。
 * 仅在组件挂载时执行一次。
 */
export function useDeepLink(onOpen: (id: number) => void) {
  const [searchParams, setSearchParams] = useSearchParams();

  useEffect(() => {
    const openId = searchParams.get('open');
    if (openId) {
      const id = parseInt(openId, 10);
      if (!isNaN(id)) {
        setTimeout(() => {
          onOpen(id);
          setSearchParams({}, { replace: true });
        }, 0);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
