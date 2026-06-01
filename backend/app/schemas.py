import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Chat ──
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=5000)
    context: Optional[str] = None
    conversation_id: Optional[str] = ""


class ChatSource(BaseModel):
    material_id: int
    filename: str
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[ChatSource] = []
    conversation_id: str = ""


class ChatHistoryItem(BaseModel):
    id: int
    conversation_id: str = ""
    question: str
    answer: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConversationItem(BaseModel):
    conversation_id: str
    title: str
    message_count: int
    last_message_at: Optional[datetime] = None


# ── Material ──
class MaterialItem(BaseModel):
    id: int
    filename: str
    file_type: str
    stored_filename: Optional[str] = ""
    status: str = "ready"
    error_message: str = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MaterialDetail(BaseModel):
    id: int
    filename: str
    file_type: str
    stored_filename: Optional[str] = ""
    preview: str = ""
    content_length: int = 0
    truncated: bool = False
    status: str = "ready"
    error_message: str = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100)


class ExportSelectedRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=100)
    include_preview: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class ParseJobItem(BaseModel):
    id: int
    material_id: int
    filename: str = ""
    status: str = "pending"
    attempts: int = 0
    error_message: str = ""
    progress_current: int = 0
    progress_total: int = 0
    progress_message: str = ""
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChunkItem(BaseModel):
    id: int
    chunk_index: int
    content: str = ""
    snippet: str = ""  # 带高亮标记的片段（query 非空时）


class SearchResult(BaseModel):
    material_id: int
    filename: str
    snippet: str


# ── Error Book ──
class ErrorBookCreate(BaseModel):
    subject: Optional[str] = ""
    chapter: Optional[str] = ""
    knowledge_point: Optional[str] = ""
    question: str = Field(..., min_length=1, max_length=10000)
    user_answer: Optional[str] = ""
    correct_answer: Optional[str] = ""
    error_type: Optional[str] = ""
    error_reason: Optional[str] = ""
    correct_approach: Optional[str] = ""
    review_suggestion: Optional[str] = ""
    tags: Optional[str] = ""
    next_review_date: Optional[str] = ""

    @field_validator("next_review_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if v and not _DATE_RE.match(v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        return v


class ErrorBookUpdate(BaseModel):
    mastered: Optional[bool] = None
    next_review_date: Optional[str] = None
    review_count: Optional[int] = None

    @field_validator("next_review_date")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is not None and v and not _DATE_RE.match(v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        return v


class ErrorBookItem(BaseModel):
    id: int
    subject: str
    chapter: str
    knowledge_point: str
    question: str
    user_answer: str
    correct_answer: str
    error_type: str
    error_reason: str
    correct_approach: str
    review_suggestion: str
    tags: str
    next_review_date: str
    mastered: bool
    review_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Study Plan ──
class StudyPlanCreate(BaseModel):
    date: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1, max_length=200)
    task: str = Field(..., min_length=1, max_length=5000)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if not _DATE_RE.match(v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        return v


class StudyPlanUpdate(BaseModel):
    completed: Optional[bool] = None


class StudyPlanItem(BaseModel):
    id: int
    date: str
    subject: str
    task: str
    completed: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanGenerateRequest(BaseModel):
    subjects: list[str] = Field(..., min_length=1, max_length=20)
    daily_hours: int = Field(default=8, ge=1, le=16)
    start_date: str = ""
    days: int = Field(default=7, ge=1, le=365)

    @field_validator("start_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        if v and not _DATE_RE.match(v):
            raise ValueError("日期格式必须为 YYYY-MM-DD")
        return v

    @field_validator("subjects")
    @classmethod
    def validate_subjects(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s.strip()]
        if not cleaned:
            raise ValueError("至少需要一个有效的科目")
        return cleaned


class PlanGenerateResponse(BaseModel):
    plans: list[StudyPlanItem]
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None


# ── Problem ──
class ProblemRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    subject: Optional[str] = ""


class ProblemResponse(BaseModel):
    solution: str


class ProblemItem(BaseModel):
    id: int
    question: str
    solution: str
    subject: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Exam ──
class ExamQuestionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    subject: Optional[str] = ""
    year: Optional[str] = ""
    question: str = Field(..., min_length=1, max_length=10000)
    answer: Optional[str] = ""
    solution: Optional[str] = ""
    tags: Optional[str] = ""

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: str) -> str:
        if v and not re.match(r"^\d{4}$", v):
            raise ValueError("年份格式必须为 YYYY")
        return v


class ExamQuestionItem(BaseModel):
    id: int
    title: str
    subject: str
    year: str
    question: str
    answer: str
    solution: str
    tags: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExamAttemptCreate(BaseModel):
    user_answer: str = ""
    is_correct: bool = False


class ExamAttemptItem(BaseModel):
    id: int
    question_id: int
    user_answer: str
    is_correct: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExamGenerateRequest(BaseModel):
    subject: str = Field(default="", max_length=100)
    topic: str = Field(..., min_length=1, max_length=500)
    count: int = Field(default=5, ge=1, le=10)
    difficulty: Optional[str] = Field(default=None, pattern=r"^(easy|medium|hard)$")
    use_materials: bool = True


class ExamDraftItem(BaseModel):
    title: str = ""
    subject: str = ""
    year: str = ""
    question: str = ""
    answer: str = ""
    solution: str = ""
    tags: str = ""


class ExamGenerateResponse(BaseModel):
    drafts: list[ExamDraftItem] = []
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None


# ── Dashboard ──
class DashboardStats(BaseModel):
    today_tasks: int
    today_completed: int
    total_materials: int
    total_errors: int
    unmastered_errors: int
    streak_days: int
    today_review_errors: int = 0
    today_study_minutes: int = 0


# ── Study Session ──
class StudySessionStartRequest(BaseModel):
    subject: str = Field(default="", max_length=100)
    note: str = Field(default="", max_length=500)
