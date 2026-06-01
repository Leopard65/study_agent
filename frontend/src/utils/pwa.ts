// PWA 工具函数：Service Worker 注册 + 安装提示 + 通知权限

let deferredPrompt: BeforeInstallPromptEvent | null = null;

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

/** 注册 Service Worker */
export function registerSW() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }
}

/** 监听安装提示事件 */
export function listenForInstallPrompt(callback: (canInstall: boolean) => void) {
  const handler = (e: Event) => {
    e.preventDefault();
    deferredPrompt = e as BeforeInstallPromptEvent;
    callback(true);
  };
  window.addEventListener('beforeinstallprompt', handler);
  return () => window.removeEventListener('beforeinstallprompt', handler);
}

/** 触发安装提示 */
export async function promptInstall(): Promise<boolean> {
  if (!deferredPrompt) return false;
  await deferredPrompt.prompt();
  const { outcome } = await deferredPrompt.userChoice;
  deferredPrompt = null;
  return outcome === 'accepted';
}

/** 请求通知权限 */
export async function requestNotificationPermission(): Promise<NotificationPermission> {
  if (!('Notification' in window)) return 'denied';
  if (Notification.permission === 'granted') return 'granted';
  if (Notification.permission === 'denied') return 'denied';
  return Notification.requestPermission();
}

/** 发送本地通知（用于错题复习提醒） */
export function sendReviewNotification(dueCount: number) {
  if (!('Notification' in window)) return;
  if (Notification.permission !== 'granted') return;
  new Notification('考研学习助手', {
    body: `你有 ${dueCount} 道错题需要复习`,
    icon: '/favicon.svg',
    tag: 'review-reminder',
  });
}
