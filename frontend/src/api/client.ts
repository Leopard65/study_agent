import axios, { isAxiosError } from 'axios';

const api = axios.create({ baseURL: '/api' });

// ── Types ──
export interface ChatSource {
  material_id: number;
  filename: string;
  snippet: string;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
  conversation_id: string;
}

export interface ChatHistoryItem {
  id: number;
  conversation_id: string;
  question: string;
  answer: string;
  created_at: string | null;
}

export interface ConversationItem {
  conversation_id: string;
  title: string;
  message_count: number;
  last_message_at: string | null;
}

export interface MaterialItem {
  id: number;
  filename: string;
  file_type: string;
  stored_filename: string | null;
  created_at: string | null;
}

export interface MaterialDetail {
  id: number;
  filename: string;
  file_type: string;
  stored_filename: string | null;
  preview: string;
  content_length: number;
  truncated: boolean;
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
  review_count: number;
  created_at: string | null;
}

export interface ErrorStats {
  total: number;
  mastered: number;
  unmastered: number;
  due_today: number;
  by_subject: { name: string; count: number }[];
  by_error_type: { name: string; count: number }[];
  by_knowledge_point: { name: string; count: number }[];
  created_last_30_days: { date: string; count: number }[];
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
  today_review_errors: number;
  today_study_minutes: number;
}

// ── Chat ──
export const chat = (question: string, context?: string, conversationId?: string): Promise<ChatResponse> =>
  api.post<ChatResponse>('/chat', { question, context, conversation_id: conversationId }).then(r => r.data);

export const getChatHistory = (conversationId?: string): Promise<ChatHistoryItem[]> =>
  api.get<ChatHistoryItem[]>('/chat/history', { params: conversationId ? { conversation_id: conversationId } : {} }).then(r => r.data);

export const listConversations = (): Promise<ConversationItem[]> =>
  api.get<ConversationItem[]>('/chat/conversations').then(r => r.data);

export const deleteConversation = (conversationId: string): Promise<OkResponse> =>
  api.delete<OkResponse>(`/chat/conversations/${conversationId}`).then(r => r.data);

// ── Materials ──
export const uploadMaterial = (file: File): Promise<MaterialItem> => {
  const fd = new FormData();
  fd.append('file', file);
  return api.post<MaterialItem>('/materials/upload', fd).then(r => r.data);
};

export const listMaterials = (limit = 20, offset = 0): Promise<MaterialItem[]> =>
  api.get<MaterialItem[]>('/materials', { params: { limit, offset } }).then(r => r.data);

export const searchMaterials = (query: string, limit = 10): Promise<MaterialSearchResult[]> =>
  api.post<MaterialSearchResult[]>('/materials/search', { query, limit }).then(r => r.data);

export const getMaterial = (id: number): Promise<MaterialDetail> =>
  api.get<MaterialDetail>(`/materials/${id}`).then(r => r.data);

export const deleteMaterial = (id: number): Promise<OkResponse> =>
  api.delete<OkResponse>(`/materials/${id}`).then(r => r.data);

export const bulkDeleteMaterials = (ids: number[]): Promise<{ deleted: number; missing: number }> =>
  api.post<{ deleted: number; missing: number }>('/materials/bulk-delete', { ids }).then(r => r.data);

export const exportSelectedMaterials = (ids: number[], includePreview = true): Promise<{ selected_count: number; materials: Record<string, unknown>[] }> =>
  api.post('/materials/export-selected', { ids, include_preview: includePreview }).then(r => r.data);

// ── Problems ──
export const solveProblem = (question: string, subject?: string): Promise<{ solution: string }> =>
  api.post<{ solution: string }>('/problems/solve', { question, subject }).then(r => r.data);

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

export const updateError = (id: number, data: { mastered?: boolean; next_review_date?: string; review_count?: number }): Promise<ErrorBookItem> =>
  api.patch<ErrorBookItem>(`/errors/${id}`, data).then(r => r.data);

export const deleteError = (id: number): Promise<OkResponse> =>
  api.delete<OkResponse>(`/errors/${id}`).then(r => r.data);

export const getErrorStats = (): Promise<ErrorStats> =>
  api.get<ErrorStats>('/errors/stats').then(r => r.data);

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

export interface TrendDay {
  date: string;
  plans_total: number;
  plans_completed: number;
  errors_created: number;
  errors_review_due: number;
  exam_attempts: number;
  exam_correct: number;
  study_minutes: number;
}

export interface TrendsResponse {
  days: number;
  items: TrendDay[];
}

export const getDashboardTrends = (days: number = 7): Promise<TrendsResponse> =>
  api.get<TrendsResponse>('/dashboard/trends', { params: { days } }).then(r => r.data);

// ── Exam ──
export interface ExamQuestionItem {
  id: number;
  title: string;
  subject: string;
  year: string;
  question: string;
  answer: string;
  solution: string;
  tags: string;
  created_at: string | null;
}

export interface ExamAttemptItem {
  id: number;
  question_id: number;
  user_answer: string;
  is_correct: boolean;
  created_at: string | null;
}

export interface ExamDraftItem {
  title: string;
  subject: string;
  year: string;
  question: string;
  answer: string;
  solution: string;
  tags: string;
}

export interface ExamGenerateResponse {
  drafts: ExamDraftItem[];
  raw_response?: string;
  parse_error?: string;
}

export const listExamQuestions = (params?: { subject?: string; year?: string; tag?: string }): Promise<ExamQuestionItem[]> =>
  api.get<ExamQuestionItem[]>('/exam/questions', { params: params || {} }).then(r => r.data);

export const createExamQuestion = (data: {
  title: string;
  subject?: string;
  year?: string;
  question: string;
  answer?: string;
  solution?: string;
  tags?: string;
}): Promise<ExamQuestionItem> => api.post<ExamQuestionItem>('/exam/questions', data).then(r => r.data);

export const generateExamQuestions = (data: {
  subject?: string;
  topic: string;
  count?: number;
  difficulty?: string;
  use_materials?: boolean;
}): Promise<ExamGenerateResponse> => api.post<ExamGenerateResponse>('/exam/generate', data).then(r => r.data);

export const submitExamAttempt = (questionId: number, data: { user_answer?: string; is_correct?: boolean }): Promise<ExamAttemptItem> =>
  api.post<ExamAttemptItem>(`/exam/questions/${questionId}/attempt`, data).then(r => r.data);

export const addExamToErrors = (questionId: number): Promise<ErrorBookItem> =>
  api.post<ErrorBookItem>(`/exam/questions/${questionId}/add-to-errors`).then(r => r.data);

export const deleteExamQuestion = (id: number): Promise<OkResponse> =>
  api.delete<OkResponse>(`/exam/questions/${id}`).then(r => r.data);

// ── Export ──
export const exportJson = (): Promise<Blob> =>
  api.get('/export/json', { responseType: 'blob' }).then(r => r.data);

// ── Import ──
export interface ImportModuleStats {
  total: number;
  new_count: number;
  conflict_count: number;
  would_insert: number;
  would_skip: number;
  would_overwrite: number;
  would_keep_both: number;
}

export interface ImportPreview {
  version: string;
  exported_at: string;
  strategy: string;
  total_conflicts: number;
  modules: Record<string, ImportModuleStats>;
  conflict_samples: Record<string, string[]>;
  // Backward compat flat fields
  materials_count: number;
  error_book_count: number;
  study_plans_count: number;
  problems_count: number;
  chat_history_count: number;
  exam_questions_count: number;
  exam_attempts_count: number;
}

export interface ImportResult {
  inserted: Record<string, number>;
  skipped: Record<string, number>;
  overwritten: Record<string, number>;
  kept_both: Record<string, number>;
}

export const importPreview = (data: Record<string, unknown>, strategy = 'skip'): Promise<ImportPreview> =>
  api.post<ImportPreview>('/import/preview', data, { params: { strategy } }).then(r => r.data);

export const importJson = (data: Record<string, unknown>, strategy = 'skip'): Promise<ImportResult> =>
  api.post<ImportResult>('/import/json', data, { params: { strategy } }).then(r => r.data);

// ── Settings ──
export const getReviewSettings = (): Promise<{ intervals: number[] }> =>
  api.get('/settings/review').then(r => r.data);

export const updateReviewSettings = (intervals: number[]): Promise<{ intervals: number[] }> =>
  api.put('/settings/review', { intervals }).then(r => r.data);

// ── Study Sessions ──
export interface StudySessionItem {
  id: number;
  subject: string;
  note: string;
  started_at: string | null;
  ended_at: string | null;
  duration_minutes: number;
  created_at: string | null;
}

export const getActiveSession = (): Promise<StudySessionItem | null> =>
  api.get<StudySessionItem | null>('/sessions/active').then(r => r.data);

export const startSession = (data?: { subject?: string; note?: string }): Promise<StudySessionItem> =>
  api.post<StudySessionItem>('/sessions/start', data || {}).then(r => r.data);

export const stopSession = (id: number): Promise<StudySessionItem> =>
  api.post<StudySessionItem>(`/sessions/${id}/stop`).then(r => r.data);

// ── Global Search ──
export interface SearchResult {
  type: string;
  id: number;
  title: string;
  snippet: string;
  created_at: string | null;
  match_field?: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export const globalSearch = (q: string, types?: string, limit?: number): Promise<SearchResponse> => {
  const params: Record<string, string | number> = { q };
  if (types) params.types = types;
  if (limit) params.limit = limit;
  return api.get<SearchResponse>('/search', { params }).then(r => r.data);
};

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
