import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import QA from './pages/QA';
import Materials from './pages/Materials';
import ProblemSolver from './pages/ProblemSolver';
import ErrorBook from './pages/ErrorBook';
import StudyPlan from './pages/StudyPlan';
import ExamPractice from './pages/ExamPractice';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-50">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/qa" element={<QA />} />
            <Route path="/materials" element={<Materials />} />
            <Route path="/problems" element={<ProblemSolver />} />
            <Route path="/errors" element={<ErrorBook />} />
            <Route path="/plan" element={<StudyPlan />} />
            <Route path="/exam" element={<ExamPractice />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
