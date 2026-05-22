import axios, { isAxiosError } from 'axios';

const api = axios.create({ baseURL: '/api' });

// ── Types ──
export interface ChatResponse {
  answer: string;
  sources: string[];
}

export interface ChatHistoryItem {
  id: number;
  question: string;
  answer: string;
  created_at: string | null;
}

export interface MaterialItem {
  id: number;
  filename: string;
  file_type: string;
  stored_filename: string | null;
  created_at: string | null;
}

export interface MaterialSearchResult {
  material_id: number;
  filename: string;
  snippet: string;
}

export interface ErrorBookItem {
  id: number;
  subject: string;
  chapter: string;
  knowledge_point: string;
  question: string;
  user_answer: string;
  correct_answer: string;
  error_type: string;
  error_reason: string;
  correct_approach: string;
  review_suggestion: string;
  tags: string;
  next_review_date: string;
  mastered: boolean;
  created_at: string | null;
}

export interface StudyPlanItem {
  id: number;
  date: string;
  subject: string;
  task: string;
  completed: boolean;
  created_at: string | null;
}

export interface PlanGenerateResponse {
  plans: StudyPlanItem[];
  raw_response?: string;
  parse_error?: string;
}

export interface ProblemItem {
  id: number;
  question: string;
  solution: string;
  subject: string;
  created_at: string | null;
}

export interface OkResponse { ok: boolean }

export interface HealthStatus {
  status: string;
  database: string;
  upload_dir: string;
  ai_configured: boolean;
  model: string;
  ocr_available: boolean;
  detail?: string;
}

export interface DashboardStats {
  today_tasks: number;
  today_completed: number;
  total_materials: number;
  total_errors: number;
  unmastered_errors: number;
  streak_days: number;
}

// ── Chat ──
export const chat = (question: string, context?: string): Promise<ChatResponse> =>
  api.post<ChatResponse>('/chat', { question, context }).then(r => r.data);

export const getChatHistory = (): Promise<ChatHistoryItem[]> =>
  api.get<ChatHistoryItem[]>('/chat/history').then(r => r.data);

// ── Materials ──
export const uploadMaterial = (file: File): Promise<MaterialItem> => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post<MaterialItem>('/materials/upload', fd).then(r => r.data);
};

export const listMaterials = (): Promise<MaterialItem[]> =>
  api.get<MaterialItem[]>('/materials').then(r => r.data);

export const searchMaterials = (query: string, limit = 10): Promise<MaterialSearchResult[]> =>
  api.post<MaterialSearchResult[]>('/materials/search', { query, limit }).then(r => r.data);

export const deleteMaterial = (id: number): Promise<OkResponse> =>
  api.delete<OkResponse>(`/materials/${id}`).then(r => r.data);

// ── Problems ──
export const solveProblem = (question: string, subject?: string): Promise<{ solution: string }> =>
  api.post<{ solution: string }>('/problems/solve', { question, subject }).then(r => r.data);

export const getProblemHistory = (): Promise<ProblemItem[]> =>
  api.get<ProblemItem[]>('/problems/history').then(r => r.data);

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
}): Promise<ErrorBookItem> => api.post<ErrorBookItem>('/errors', data).then(r => r.data);

export const listErrors = (mastered?: boolean, subject?: string): Promise<ErrorBookItem[]> => {
  const params: Record<string, string> = {};
  if (mastered !== undefined) params.mastered = String(mastered);
  if (subject) params.subject = subject;
  return api.get<ErrorBookItem[]>('/errors', { params }).then(r => r.data);
};

export const updateError = (id: number, data: { mastered?: boolean; next_review_date?: string }): Promise<ErrorBookItem> =>
  api.patch<ErrorBookItem>(`/errors/${id}`, data).then(r => r.data);

export const deleteError = (id: number): Promise<OkResponse> =>
  api.delete<OkResponse>(`/errors/${id}`).then(r => r.data);

// ── Study Plan ──
export const createPlan = (data: { date: string; subject: string; task: string }): Promise<StudyPlanItem> =>
  api.post<StudyPlanItem>('/plan', data).then(r => r.data);

export const listPlans = (date?: string): Promise<StudyPlanItem[]> =>
  api.get<StudyPlanItem[]>('/plan', { params: date ? { date } : {} }).then(r => r.data);

export const updatePlan = (id: number, completed: boolean): Promise<StudyPlanItem> =>
  api.patch<StudyPlanItem>(`/plan/${id}`, { completed }).then(r => r.data);

export const deletePlan = (id: number): Promise<OkResponse> =>
  api.delete<OkResponse>(`/plan/${id}`).then(r => r.data);

export const generatePlan = (data: {
  subjects: string[];
  daily_hours?: number;
  start_date?: string;
  days?: number;
}): Promise<PlanGenerateResponse> => api.post<PlanGenerateResponse>('/plan/generate', data).then(r => r.data);

// ── Dashboard ──
export const getDashboard = (): Promise<DashboardStats> =>
  api.get<DashboardStats>('/dashboard').then(r => r.data);

// ── Health ──
export const getHealth = (): Promise<HealthStatus> =>
  api.get<HealthStatus>('/health').then(r => r.data);

export default api;

export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const data = err.response?.data;
    if (typeof data?.detail === 'string') return data.detail;
    if (typeof data?.message === 'string') return data.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
