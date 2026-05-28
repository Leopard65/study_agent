import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'system';

interface Preferences {
  sidebarCollapsed: boolean;
  theme: Theme;
}

interface PreferencesContextType extends Preferences {
  setSidebarCollapsed: (v: boolean) => void;
  setTheme: (t: Theme) => void;
}

const STORAGE_KEY = 'math_agent_preferences';

const defaults: Preferences = {
  sidebarCollapsed: false,
  theme: 'system',
};

function loadPreferences(): Preferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...defaults, ...parsed };
    }
  } catch { /* ignore */ }
  return defaults;
}

function savePreferences(p: Preferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(p));
  } catch { /* ignore */ }
}

const PreferencesContext = createContext<PreferencesContextType | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences);

  // Apply dark mode class to <html>
  useEffect(() => {
    const root = document.documentElement;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');

    function apply(theme: Theme) {
      const dark = theme === 'dark' || (theme === 'system' && mq.matches);
      root.classList.toggle('dark', dark);
    }

    apply(prefs.theme);

    if (prefs.theme === 'system') {
      const handler = () => apply('system');
      mq.addEventListener('change', handler);
      return () => mq.removeEventListener('change', handler);
    }
  }, [prefs.theme]);

  const setSidebarCollapsed = (v: boolean) => {
    setPrefs(prev => {
      const next = { ...prev, sidebarCollapsed: v };
      savePreferences(next);
      return next;
    });
  };

  const setTheme = (t: Theme) => {
    setPrefs(prev => {
      const next = { ...prev, theme: t };
      savePreferences(next);
      return next;
    });
  };

  return (
    <PreferencesContext.Provider value={{ ...prefs, setSidebarCollapsed, setTheme }}>
      {children}
    </PreferencesContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePreferences() {
  const ctx = useContext(PreferencesContext);
  if (!ctx) throw new Error('usePreferences must be used within PreferencesProvider');
  return ctx;
}
