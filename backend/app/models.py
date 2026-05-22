from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, func
from app.database import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    content = Column(Text, default="")
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
