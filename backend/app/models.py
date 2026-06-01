from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from app.database import Base


class MaterialParseJob(Base):
    __tablename__ = "material_parse_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False)  # pending / processing / done / failed / cancelled
    attempts = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, default="")
    progress_current = Column(Integer, default=0)   # 当前完成步骤数
    progress_total = Column(Integer, default=0)      # 总步骤数（0 = 未知/无阶段）
    progress_message = Column(String(200), default="")  # 当前阶段描述
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    content = Column(Text, default="")
    stored_filename = Column(String(500), default="")
    status = Column(String(20), default="ready")  # pending / processing / ready / failed
    error_message = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class MaterialChunk(Base):
    __tablename__ = "material_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(Integer, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(50), default="", index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class ErrorBook(Base):
    __tablename__ = "error_book"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(100), default="")
    chapter = Column(String(200), default="")
    knowledge_point = Column(String(300), default="")
    question = Column(Text, nullable=False)
    user_answer = Column(Text, default="")
    correct_answer = Column(Text, default="")
    error_type = Column(String(100), default="")
    error_reason = Column(Text, default="")
    correct_approach = Column(Text, default="")
    review_suggestion = Column(Text, default="")
    tags = Column(String(500), default="")
    next_review_date = Column(String(10), default="")
    mastered = Column(Boolean, default=False)
    review_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), nullable=False)
    subject = Column(String(100), nullable=False)
    task = Column(Text, nullable=False)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class ProblemRecord(Base):
    __tablename__ = "problems"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    solution = Column(Text, default="")
    subject = Column(String(100), default="")
    created_at = Column(DateTime, server_default=func.now())


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    subject = Column(String(100), default="")
    year = Column(String(10), default="")
    question = Column(Text, nullable=False)
    answer = Column(Text, default="")
    solution = Column(Text, default="")
    tags = Column(String(500), default="")
    created_at = Column(DateTime, server_default=func.now())


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    question_id = Column(Integer, nullable=False, index=True)
    user_answer = Column(Text, default="")
    is_correct = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject = Column(String(100), default="")
    note = Column(Text, default="")
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
