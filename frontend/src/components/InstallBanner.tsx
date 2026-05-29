import { useState, useEffect } from 'react';
import { listenForInstallPrompt, promptInstall } from '../utils/pwa';

export default function InstallBanner() {
  const [canInstall, setCanInstall] = useState(false);
  const [dismissed, setDismissed] = useState(() => {
    return sessionStorage.getItem('pwa_install_dismissed') === '1';
  });

  useEffect(() => {
    const cleanup = listenForInstallPrompt(setCanInstall);
    return cleanup;
  }, []);

  if (!canInstall || dismissed) return null;

  const handleInstall = async () => {
    const accepted = await promptInstall();
    if (accepted) setCanInstall(false);
  };

  const handleDismiss = () => {
    setDismissed(true);
    sessionStorage.setItem('pwa_install_dismissed', '1');
  };

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-80 z-50 bg-white dark:bg-gray-800 border dark:border-gray-700 rounded-xl shadow-lg p-4 flex items-center gap-3">
      <div className="text-2xl">📱</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium dark:text-gray-100">安装到桌面</div>
        <div className="text-xs text-gray-500 dark:text-gray-400">添加到主屏幕，获得更好体验</div>
      </div>
      <div className="flex gap-1.5 shrink-0">
        <button
          onClick={handleInstall}
          className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs hover:bg-blue-700"
        >安装</button>
        <button
          onClick={handleDismiss}
          className="px-2 py-1.5 text-gray-400 hover:text-gray-600 text-xs"
        >✕</button>
      </div>
    </div>
  );
}
