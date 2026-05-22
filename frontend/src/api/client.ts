import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

// ── Chat ──
export const chat = (question: string, context?: string) =>
  api.post<{ answer: string; sources: string[] }>('/chat', { question, context }).then(r => r.data);

export const getChatHistory = () =>
  api.get('/chat/history').then(r => r.data);

// ── Materials ──
export const uploadMaterial = (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post('/materials/upload', fd).then(r => r.data);
};

export const listMaterials = () =>
  api.get('/materials').then(r => r.data);

export const searchMaterials = (query: string, limit = 10) =>
  api.post('/materials/search', { query, limit }).then(r => r.data);

export const deleteMaterial = (id: number) =>
  api.delete(`/materials/${id}`);

// ── Problems ──
export const solveProblem = (question: string, subject?: string) =>
  api.post<{ solution: string }>('/problems/solve', { question, subject }).then(r => r.data);

export const getProblemHistory = () =>
  api.get('/problems/history').then(r => r.data);

// ── Error Book ──
export const createError = (data: {
  question: string;
  subject?: string;
  chapter?: string;
  knowledge_point?: string;
  user_answer?: string;
  correct_answer?: string;
  error_type?: string;
  error_reason?: string;
  correct_approach?: string;
  review_suggestion?: string;
  tags?: string;
  next_review_date?: string;
}) => api.post('/errors', data).then(r => r.data);

export const listErrors = (mastered?: boolean, subject?: string) => {
  const params: Record<string, string> = {};
  if (mastered !== undefined) params.mastered = String(mastered);
  if (subject) params.subject = subject;
  return api.get('/errors', { params }).then(r => r.data);
};

export const updateError = (id: number, data: { mastered?: boolean; next_review_date?: string }) =>
  api.patch(`/errors/${id}`, data).then(r => r.data);

export const deleteError = (id: number) =>
  api.delete(`/errors/${id}`);

// ── Study Plan ──
export const createPlan = (data: { date: string; subject: string; task: string }) =>
  api.post('/plan', data).then(r => r.data);

export const listPlans = (date?: string) =>
  api.get('/plan', { params: date ? { date } : {} }).then(r => r.data);

export const updatePlan = (id: number, completed: boolean) =>
  api.patch(`/plan/${id}`, { completed }).then(r => r.data);

export const deletePlan = (id: number) =>
  api.delete(`/plan/${id}`);

export const generatePlan = (data: {
  subjects: string[];
  daily_hours?: number;
  start_date?: string;
  days?: number;
}) => api.post<{ plans: any[]; raw_response?: string; parse_error?: string }>('/plan/generate', data).then(r => r.data);

// ── Dashboard ──
export const getDashboard = () =>
  api.get('/dashboard').then(r => r.data);

export default api;
