import { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { PreferencesProvider } from './hooks/usePreferences';
import Sidebar from './components/Sidebar';
import CommandPalette from './components/CommandPalette';
import InstallBanner from './components/InstallBanner';
import { exportJson } from './api/client';
import { downloadBlob } from './utils/constants';

const Dashboard = lazy(() => import('./pages/Dashboard'));
const QA = lazy(() => import('./pages/QA'));
const Materials = lazy(() => import('./pages/Materials'));
const ProblemSolver = lazy(() => import('./pages/ProblemSolver'));
const ErrorBook = lazy(() => import('./pages/ErrorBook'));
const StudyPlan = lazy(() => import('./pages/StudyPlan'));
const ExamPractice = lazy(() => import('./pages/ExamPractice'));
const SearchPage = lazy(() => import('./pages/SearchPage'));
const ReviewQueue = lazy(() => import('./pages/ReviewQueue'));

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="text-gray-400 dark:text-gray-500 text-sm">加载中…</div>
    </div>
  );
}

function AppInner() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const handleExport = useCallback(async () => {
    try {
      const blob = await exportJson();
      const date = new Date().toISOString().slice(0, 10);
      downloadBlob(blob, `math_agent_backup_${date}.json`);
    } catch {
      // Sidebar 会显示导出错误，这里静默处理
    }
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(prev => !prev);
      }
      if (e.key === 'Escape' && mobileSidebarOpen) {
        setMobileSidebarOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [mobileSidebarOpen]);

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Mobile hamburger */}
      {!mobileSidebarOpen && (
        <button
          onClick={() => setMobileSidebarOpen(true)}
          className="fixed top-3 left-3 z-30 md:hidden p-2 rounded bg-gray-900 text-gray-100 shadow-lg"
          aria-label="打开菜单"
        >
          ☰
        </button>
      )}

      <Sidebar
        onOpenPalette={() => setPaletteOpen(true)}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />
      <main className="flex-1 overflow-auto">
        <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/qa" element={<QA />} />
          <Route path="/materials" element={<Materials />} />
          <Route path="/problems" element={<ProblemSolver />} />
          <Route path="/errors" element={<ErrorBook />} />
          <Route path="/plan" element={<StudyPlan />} />
          <Route path="/exam" element={<ExamPractice />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/review" element={<ReviewQueue />} />
        </Routes>
        </Suspense>
      </main>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onExport={handleExport} />
      <InstallBanner />
    </div>
  );
}

export default function App() {
  return (
    <PreferencesProvider>
      <BrowserRouter>
        <AppInner />
      </BrowserRouter>
    </PreferencesProvider>
  );
}
