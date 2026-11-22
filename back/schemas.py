from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator



# БАЗОВАЯ СХЕМА
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)



# АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ
class UserRegister(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Некорректный Email")
        local_part, domain = value.split("@", 1)
        if not local_part or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("Некорректный Email")
        return value


class UserLogin(BaseModel):
    email: str
    password: str
    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


# ПОЛЬЗОВАТЕЛИ
class UserResponse(BaseSchema):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime


class UserAdminResponse(UserResponse):
    attempts: int = 0
    completed_exercises: int = 0
    progress_percent: float = 0.0


# КУРСЫ
class CourseCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class CourseResponse(BaseSchema):
    id: int
    slug: str
    title: str
    description: str | None
    is_active: bool
    created_at: datetime


# УРОКИ
class LessonCreate(BaseModel):
    course_id: int
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    content: str | None = None
    level: str
    order_index: int = 0
    is_active: bool = True

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        allowed_levels = {"beginner", "intermediate", "advanced"}

        if value not in allowed_levels:
            raise ValueError("Недопустимый уровень обучения")

        return value


class LessonResponse(BaseSchema):
    id: int
    course_id: int
    slug: str
    title: str
    description: str | None
    content: str | None
    level: str
    order_index: int
    is_active: bool


# ЗАДАНИЯ
class ExerciseResponse(BaseSchema):
    id: int
    lesson_id: int
    slug: str
    title: str
    description: str
    order_index: int
    is_active: bool


class ExerciseCreate(BaseModel):
    lesson_id: int
    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str
    folder_path: str = Field(min_length=1, max_length=500)
    order_index: int = 0
    is_active: bool = True


# ВЫПОЛНЕНИЕ SQL-ЗАПРОСОВ
class SQLSubmission(BaseModel):
    query: str = Field(min_length=1, max_length=10000)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("SQL-запрос не может быть пустым")

        return value


class SQLExecutionResponse(BaseModel):
    success: bool
    columns: list[str] = []
    rows: list[list[Any]] = []
    message: str | None = None


class ExerciseCheckResponse(BaseModel):
    is_correct: bool
    message: str
    columns: list[str] = []
    rows: list[list[Any]] = []


# ИСТОРИЯ ПОПЫТОК
class ExerciseAttemptResponse(BaseSchema):
    id: int
    user_id: int
    exercise_id: int
    submitted_query: str
    is_correct: bool
    result_message: str | None
    created_at: datetime



# ПРОГРЕСС ОБУЧЕНИЯ
class LessonProgressResponse(BaseSchema):
    id: int
    user_id: int
    lesson_id: int
    is_completed: bool
    completed_at: datetime | None


class LessonCompletionRequest(BaseModel):
    is_completed: bool = True


class ProgressResponse(BaseModel):
    total_exercises: int
    completed_exercises: int
    progress_percent: float