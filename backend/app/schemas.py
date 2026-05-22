from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# ── Chat ──
class ChatRequest(BaseModel):
    question: str
    context: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []


class ChatHistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Material ──
class MaterialItem(BaseModel):
    id: int
    filename: str
    file_type: str
    stored_filename: Optional[str] = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    limit: int = 10


class SearchResult(BaseModel):
    material_id: int
    filename: str
    snippet: str


# ── Error Book ──
class ErrorBookCreate(BaseModel):
    subject: Optional[str] = ""
    chapter: Optional[str] = ""
    knowledge_point: Optional[str] = ""
    question: str
    user_answer: Optional[str] = ""
    correct_answer: Optional[str] = ""
    error_type: Optional[str] = ""
    error_reason: Optional[str] = ""
    correct_approach: Optional[str] = ""
    review_suggestion: Optional[str] = ""
    tags: Optional[str] = ""
    next_review_date: Optional[str] = ""


class ErrorBookUpdate(BaseModel):
    mastered: Optional[bool] = None
    next_review_date: Optional[str] = None


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
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Study Plan ──
class StudyPlanCreate(BaseModel):
    date: str
    subject: str
    task: str


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
    subjects: list[str]
    daily_hours: int = 8
    start_date: str = ""
    days: int = 7


class PlanGenerateResponse(BaseModel):
    plans: list[StudyPlanItem]
    raw_response: Optional[str] = None
    parse_error: Optional[str] = None


# ── Problem ──
class ProblemRequest(BaseModel):
    question: str
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


# ── Dashboard ──
class DashboardStats(BaseModel):
    today_tasks: int
    today_completed: int
    total_materials: int
    total_errors: int
    unmastered_errors: int
    streak_days: int
