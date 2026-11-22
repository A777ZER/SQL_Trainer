
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
    Cookie,
)
from pydantic import BaseModel, Field
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from back.database import get_db
from back.models import (
    User,
    Course,
    Lesson,
    Exercise,
    ExerciseAttempt,
    LessonProgress,
)
from back.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
    UserAdminResponse,
    CourseCreate,
    CourseResponse,
    LessonCreate,
    LessonResponse,
    ExerciseResponse,
    SQLSubmission,
    SQLExecutionResponse,
    ExerciseCheckResponse,
    ExerciseAttemptResponse,
    LessonProgressResponse,
    LessonCompletionRequest,
    ProgressResponse,
    ExerciseCreate,
)
from back.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)
from back.sql_engine import run_query, check_query
from back.config import settings


# ============================================================
# ОСНОВНОЙ МАРШРУТИЗАТОР
# ============================================================

router = APIRouter(prefix="/api")


# ============================================================
# ЗАВИСИМОСТЬ: ТЕКУЩИЙ ПОЛЬЗОВАТЕЛЬ
# ============================================================

def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация",
        )

    payload = decode_access_token(access_token)

    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен авторизации",
        )

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный токен авторизации",
        )

    user = db.get(User, user_id)

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или заблокирован",
        )

    return user


# ============================================================
# ЗАВИСИМОСТЬ: ПРОВЕРКА ПРАВ АДМИНИСТРАТОРА
# ============================================================

def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:

    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав",
        )

    return current_user


# ============================================================
# АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ
# ============================================================

@router.post(
    "/auth/register",
    tags=["Авторизация"],
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db),
):

    existing_user = db.scalar(
        select(User).where(User.email == user_data.email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким Email уже существует",
        )

    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        role="student",
        is_active=True,
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось создать пользователя",
        )

    return user


@router.post("/auth/login", tags=["Авторизация"])
def login_user(
    user_data: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):

    user = db.scalar(
        select(User).where(User.email == user_data.email)
    )

    if not user or not verify_password(
        user_data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный Email или пароль",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )

    access_token = create_access_token(
        user_id=user.id,
        role=user.role,
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60,
        path="/",
    )

    return {
        "message": "Авторизация успешна",
        "user": UserResponse.model_validate(user),
    }


@router.post("/auth/logout", tags=["Авторизация"])
def logout_user(response: Response):

    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )

    return {
        "message": "Выход выполнен успешно"
    }


@router.get(
    "/auth/me",
    tags=["Авторизация"],
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
):

    return current_user


# ============================================================
# КУРСЫ
# ============================================================

@router.get(
    "/courses",
    tags=["Курсы"],
    response_model=list[CourseResponse],
)
def get_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    return db.scalars(
        select(Course)
        .where(Course.is_active.is_(True))
        .order_by(Course.id)
    ).all()


@router.post(
    "/courses",
    tags=["Курсы"],
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    course_data: CourseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    existing_course = db.scalar(
        select(Course).where(Course.slug == course_data.slug)
    )

    if existing_course:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Курс с таким идентификатором уже существует",
        )

    course = Course(**course_data.model_dump())

    db.add(course)
    db.commit()
    db.refresh(course)

    return course


# ============================================================
# УРОКИ
# ============================================================

@router.get(
    "/lessons",
    tags=["Уроки"],
    response_model=list[LessonResponse],
)
def get_lessons(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = select(Lesson).where(
        Lesson.is_active.is_(True),
        Lesson.course_id.in_(
            select(Course.id).where(Course.is_active.is_(True))
        ),
    )

    if course_id is not None:
        query = query.where(Lesson.course_id == course_id)

    return db.scalars(
        query.order_by(Lesson.order_index, Lesson.id)
    ).all()


@router.post(
    "/lessons",
    tags=["Уроки"],
    response_model=LessonResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lesson(
    lesson_data: LessonCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    course = db.get(Course, lesson_data.course_id)

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Курс не найден",
        )

    existing_lesson = db.scalar(
        select(Lesson).where(Lesson.slug == lesson_data.slug)
    )

    if existing_lesson:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Урок с таким идентификатором уже существует",
        )

    lesson = Lesson(**lesson_data.model_dump())

    db.add(lesson)
    db.commit()
    db.refresh(lesson)

    return lesson


# ============================================================
# СОЗДАНИЕ ЗАДАНИЙ
# ============================================================

@router.post(
    "/exercises",
    tags=["Задания"],
    response_model=ExerciseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exercise(
    exercise_data: ExerciseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    lesson = db.get(Lesson, exercise_data.lesson_id)

    if not lesson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Урок не найден",
        )

    existing_exercise = db.scalar(
        select(Exercise).where(
            Exercise.slug == exercise_data.slug
        )
    )

    if existing_exercise:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Задание с таким идентификатором уже существует",
        )

    exercise_folder = Path(
        exercise_data.folder_path
    )

    if not exercise_folder.is_absolute():
        exercise_folder = (
            settings.exercises_dir / exercise_folder
        )

    try:
        exercise_folder = exercise_folder.resolve()
        exercises_root = settings.exercises_dir.resolve()

        if not exercise_folder.is_relative_to(exercises_root):
            raise ValueError("Недопустимый путь к заданию")

        if not (exercise_folder / "setup.sql").is_file():
            raise ValueError("Не найден setup.sql")

        if not (exercise_folder / "solution.sql").is_file():
            raise ValueError("Не найден solution.sql")

    except (ValueError, OSError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    exercise = Exercise(
        **exercise_data.model_dump()
    )

    db.add(exercise)
    db.commit()
    db.refresh(exercise)

    return exercise


# ============================================================
# ПОЛУЧЕНИЕ ЗАДАНИЙ
# ============================================================

@router.get(
    "/exercises",
    tags=["Задания"],
    response_model=list[ExerciseResponse],
)
def get_exercises(
    lesson_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = (
        select(Exercise)
        .join(Lesson)
        .join(Course)
        .where(
            Exercise.is_active.is_(True),
            Lesson.is_active.is_(True),
            Course.is_active.is_(True),
        )
    )

    if lesson_id is not None:
        query = query.where(
            Exercise.lesson_id == lesson_id
        )

    return db.scalars(
        query.order_by(Exercise.order_index, Exercise.id)
    ).all()


# ============================================================
# ВЫПОЛНЕНИЕ SQL-ЗАПРОСА
# ============================================================

@router.post(
    "/exercises/{exercise_id}/run",
    tags=["Задания"],
    response_model=SQLExecutionResponse,
)
def execute_exercise_query(
    exercise_id: int,
    query_data: SQLSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    exercise = db.scalar(
        select(Exercise)
        .join(Lesson)
        .join(Course)
        .where(
            Exercise.id == exercise_id,
            Exercise.is_active.is_(True),
            Lesson.is_active.is_(True),
            Course.is_active.is_(True),
        )
    )

    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    result = run_query(
        exercise.folder_path,
        query_data.query,
    )

    return SQLExecutionResponse(**result)


# ============================================================
# ПРОВЕРКА РЕШЕНИЯ И СОХРАНЕНИЕ ПОПЫТКИ
# ============================================================

@router.post(
    "/exercises/{exercise_id}/check",
    tags=["Задания"],
    response_model=ExerciseCheckResponse,
)
def check_exercise_solution(
    exercise_id: int,
    query_data: SQLSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    exercise = db.scalar(
        select(Exercise)
        .join(Lesson)
        .join(Course)
        .where(
            Exercise.id == exercise_id,
            Exercise.is_active.is_(True),
            Lesson.is_active.is_(True),
            Course.is_active.is_(True),
        )
    )

    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задание не найдено",
        )

    result = check_query(
        exercise.folder_path,
        query_data.query,
    )

    attempt = ExerciseAttempt(
        user_id=current_user.id,
        exercise_id=exercise.id,
        submitted_query=query_data.query,
        is_correct=result["is_correct"],
        result_message=result["message"],
    )

    db.add(attempt)
    db.commit()

    return ExerciseCheckResponse(**result)


# ============================================================
# ИСТОРИЯ ПОПЫТОК
# ============================================================

@router.get(
    "/attempts",
    tags=["Попытки"],
    response_model=list[ExerciseAttemptResponse],
)
def get_attempts(
    exercise_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    query = select(ExerciseAttempt)

    if current_user.role != "admin":
        query = query.where(
            ExerciseAttempt.user_id == current_user.id
        )

    if exercise_id is not None:
        query = query.where(
            ExerciseAttempt.exercise_id == exercise_id
        )

    return db.scalars(
        query.order_by(ExerciseAttempt.created_at.desc())
    ).all()


# ============================================================
# ПРОГРЕСС ОБУЧЕНИЯ
# ============================================================

@router.get(
    "/progress",
    tags=["Прогресс"],
    response_model=ProgressResponse,
)
def get_progress(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    total_exercises = db.scalar(
        select(func.count(Exercise.id))
        .join(Lesson)
        .join(Course)
        .where(
            Exercise.is_active.is_(True),
            Lesson.is_active.is_(True),
            Course.is_active.is_(True),
        )
    ) or 0

    completed_exercises = db.scalar(
        select(func.count(distinct(ExerciseAttempt.exercise_id)))
        .join(Exercise)
        .join(Lesson)
        .join(Course)
        .where(
            ExerciseAttempt.user_id == current_user.id,
            ExerciseAttempt.is_correct.is_(True),
            Exercise.is_active.is_(True),
            Lesson.is_active.is_(True),
            Course.is_active.is_(True),
        )
    ) or 0

    progress_percent = (
        completed_exercises / total_exercises * 100
        if total_exercises > 0
        else 0.0
    )

    return ProgressResponse(
        total_exercises=total_exercises,
        completed_exercises=completed_exercises,
        progress_percent=round(progress_percent, 2),
    )


# ============================================================
# ЗАВЕРШЕНИЕ УРОКА
# ============================================================

@router.post(
    "/lessons/{lesson_id}/complete",
    tags=["Уроки"],
    response_model=LessonProgressResponse,
)
def complete_lesson(
    lesson_id: int,
    completion_data: LessonCompletionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    lesson = db.get(Lesson, lesson_id)

    if not lesson or not lesson.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Урок не найден",
        )

    progress = db.scalar(
        select(LessonProgress).where(
            LessonProgress.user_id == current_user.id,
            LessonProgress.lesson_id == lesson_id,
        )
    )

    if not progress:
        progress = LessonProgress(
            user_id=current_user.id,
            lesson_id=lesson_id,
        )
        db.add(progress)

    progress.is_completed = completion_data.is_completed

    progress.completed_at = (
        datetime.now(timezone.utc)
        if completion_data.is_completed
        else None
    )

    db.commit()
    db.refresh(progress)

    return progress


# ============================================================
# ПРОГРЕСС СТУДЕНТОВ ДЛЯ АДМИНИСТРАТОРА
# ============================================================

@router.get(
    "/admin/students",
    tags=["Администрирование"],
    response_model=list[UserAdminResponse],
)
def get_students_progress(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):

    students = db.scalars(
        select(User)
        .where(User.role == "student")
        .order_by(User.id)
    ).all()

    total_exercises = db.scalar(
        select(func.count(Exercise.id))
        .join(Lesson)
        .join(Course)
        .where(
            Exercise.is_active.is_(True),
            Lesson.is_active.is_(True),
            Course.is_active.is_(True),
        )
    ) or 0

    result = []

    for student in students:

        attempts_count = db.scalar(
            select(func.count(ExerciseAttempt.id))
            .where(ExerciseAttempt.user_id == student.id)
        ) or 0

        completed_count = db.scalar(
            select(func.count(distinct(ExerciseAttempt.exercise_id)))
            .join(Exercise)
            .join(Lesson)
            .join(Course)
            .where(
                ExerciseAttempt.user_id == student.id,
                ExerciseAttempt.is_correct.is_(True),
                Exercise.is_active.is_(True),
                Lesson.is_active.is_(True),
                Course.is_active.is_(True),
            )
        ) or 0

        progress_percent = (
            completed_count / total_exercises * 100
            if total_exercises > 0
            else 0.0
        )

        result.append(
            UserAdminResponse(
                id=student.id,
                email=student.email,
                role=student.role,
                is_active=student.is_active,
                created_at=student.created_at,
                attempts=attempts_count,
                completed_exercises=completed_count,
                progress_percent=round(progress_percent, 2),
            )
        )

    return result
