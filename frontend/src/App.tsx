import { useCallback, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { PreferencesProvider } from './hooks/usePreferences';
import Sidebar from './components/Sidebar';
import CommandPalette from './components/CommandPalette';
import Dashboard from './pages/Dashboard';
import QA from './pages/QA';
import Materials from './pages/Materials';
import ProblemSolver from './pages/ProblemSolver';
import ErrorBook from './pages/ErrorBook';
import StudyPlan from './pages/StudyPlan';
import ExamPractice from './pages/ExamPractice';
import SearchPage from './pages/SearchPage';
import { exportJson, getApiErrorMessage } from './api/client';

function AppInner() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  const handleExport = useCallback(async () => {
    try {
      const blob = await exportJson();
      const date = new Date().toISOString().slice(0, 10);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `math_agent_backup_${date}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert(getApiErrorMessage(null, '导出失败'));
    }
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900">
      <Sidebar onOpenPalette={() => setPaletteOpen(true)} />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/qa" element={<QA />} />
          <Route path="/materials" element={<Materials />} />
          <Route path="/problems" element={<ProblemSolver />} />
          <Route path="/errors" element={<ErrorBook />} />
          <Route path="/plan" element={<StudyPlan />} />
          <Route path="/exam" element={<ExamPractice />} />
          <Route path="/search" element={<SearchPage />} />
        </Routes>
      </main>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onExport={handleExport} />
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
