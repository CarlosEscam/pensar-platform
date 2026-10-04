from sqlalchemy import Column, Integer, String, Enum, DateTime, func
from ..database import Base
import enum


class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.STUDENT)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relaciones (las definiremos después)
    # student_profile = relationship("StudentProfile", back_populates="user", uselist=False)
    # groups = relationship("Group", back_populates="teacher")
