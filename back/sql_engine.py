import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from back.config import settings


# ============================================================
# НАСТРОЙКИ SQL ENGINE
# ============================================================

# Максимальное время выполнения запроса (секунды)
QUERY_TIMEOUT = 5

# Максимальное количество возвращаемых строк
MAX_RESULT_ROWS = 1000


# ============================================================
# ПОИСК ФАЙЛОВ ЗАДАНИЯ
# ============================================================

def get_exercise_folder(folder_path: str | Path) -> Path:
    """
    Получает путь к папке задания.
    """

    folder_path = Path(folder_path)

    if not folder_path.is_absolute():
        folder_path = settings.exercises_dir / folder_path

    folder_path = folder_path.resolve()

    exercises_root = settings.exercises_dir.resolve()

    if not folder_path.is_relative_to(exercises_root):
        raise ValueError("Недопустимый путь к заданию")

    if not folder_path.is_dir():
        raise FileNotFoundError("Папка задания не найдена")

    return folder_path


# ============================================================
# ЗАГРУЗКА SQL-ФАЙЛОВ
# ============================================================

def load_sql_file(file_path: Path) -> str:
    """
    Загружает содержимое SQL-файла.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"SQL-файл не найден: {file_path.name}")

    return file_path.read_text(encoding="utf-8")


# ============================================================
# СОЗДАНИЕ УЧЕБНОЙ БАЗЫ ДАННЫХ
# ============================================================

def create_training_database(
    exercise_folder: str | Path
) -> sqlite3.Connection:
    """
    Создаёт временную учебную SQLite-базу
    и заполняет её данными из setup.sql.
    """

    exercise_folder = get_exercise_folder(exercise_folder)

    setup_sql = load_sql_file(
        exercise_folder / "setup.sql"
    )

    # Создаём временный файл базы данных
    temporary_file = tempfile.NamedTemporaryFile(
        suffix=".db",
        delete=False
    )

    database_path = temporary_file.name
    temporary_file.close()

    # Подключаемся к временной базе
    connection = sqlite3.connect(
        database_path,
        timeout=QUERY_TIMEOUT
    )

    try:
        # Создаём структуру таблиц и добавляем данные
        connection.executescript(setup_sql)

        # Сохраняем изменения setup.sql
        connection.commit()

        return connection

    except Exception:
        connection.close()

        Path(database_path).unlink(missing_ok=True)

        raise


# ============================================================
# ЗАЩИТА SQL-ЗАПРОСОВ
# ============================================================

def configure_query_security(
    connection: sqlite3.Connection
) -> None:
    """
    Настраивает защиту учебной базы данных
    от изменения структуры и данных.
    """

    # Запрещаем изменение базы данных
    connection.execute("PRAGMA query_only = ON")

    # Запрещаем выполнение опасных SQL-операций
    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_RECURSIVE
    }

    def authorizer(
        action: int,
        arg1: str | None,
        arg2: str | None,
        database_name: str | None,
        trigger_name: str | None
    ) -> int:

        if action in allowed_actions:
            # Дополнительно запрещаем опасную функцию
            if action == sqlite3.SQLITE_FUNCTION:
                function_name = (arg2 or arg1 or "").lower()

                if function_name == "load_extension":
                    return sqlite3.SQLITE_DENY

            return sqlite3.SQLITE_OK

        return sqlite3.SQLITE_DENY

    connection.set_authorizer(authorizer)


# ============================================================
# ВЫПОЛНЕНИЕ SQL-ЗАПРОСА
# ============================================================

def execute_sql(
    connection: sqlite3.Connection,
    query: str
) -> dict[str, Any]:
    """
    Выполняет SQL-запрос и возвращает результат.
    """

    query = query.strip()

    if not query:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "message": "SQL-запрос пустой"
        }

    # Разрешаем только SELECT и WITH
    normalized_query = query.lstrip().upper()

    if not (
        normalized_query.startswith("SELECT")
        or normalized_query.startswith("WITH")
    ):
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "message": "Разрешены только SELECT-запросы"
        }

    # Ограничиваем время выполнения запроса
    start_time = time.monotonic()

    def progress_handler() -> int:
        if time.monotonic() - start_time > QUERY_TIMEOUT:
            return 1

        return 0

    connection.set_progress_handler(
        progress_handler,
        1000
    )

    try:
        cursor = connection.execute(query)

        # Получаем названия столбцов
        columns = [
            column[0]
            for column in cursor.description
        ] if cursor.description else []

        # Получаем ограниченное количество строк
        rows = cursor.fetchmany(MAX_RESULT_ROWS + 1)

        if len(rows) > MAX_RESULT_ROWS:
            return {
                "success": False,
                "columns": columns,
                "rows": [],
                "message": (
                    f"Результат превышает лимит "
                    f"{MAX_RESULT_ROWS} строк"
                )
            }

        return {
            "success": True,
            "columns": columns,
            "rows": [list(row) for row in rows],
            "message": "Запрос выполнен успешно"
        }

    except sqlite3.Error as error:
        error_message = str(error)

        if "interrupted" in error_message.lower():
            error_message = (
                f"Превышено время выполнения запроса "
                f"({QUERY_TIMEOUT} секунд)"
            )

        return {
            "success": False,
            "columns": [],
            "rows": [],
            "message": error_message
        }

    finally:
        connection.set_progress_handler(None, 0)


# ============================================================
# ЗАПУСК SQL-ЗАПРОСА В УЧЕБНОЙ БАЗЕ
# ============================================================

def run_query(
    exercise_folder: str | Path,
    query: str
) -> dict[str, Any]:
    """
    Создаёт учебную базу и выполняет запрос студента.
    """

    connection = None
    database_path = None

    try:
        connection = create_training_database(
            exercise_folder
        )

        database_path = Path(
            connection.execute("PRAGMA database_list").fetchone()[2]
        )

        configure_query_security(connection)

        return execute_sql(connection, query)

    except Exception as error:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "message": str(error)
        }

    finally:
        if connection is not None:
            connection.close()

        if database_path is not None:
            database_path.unlink(missing_ok=True)


# ============================================================
# ПРОВЕРКА РЕШЕНИЯ ЗАДАНИЯ
# ============================================================

def check_query(
    exercise_folder: str | Path,
    student_query: str
) -> dict[str, Any]:
    """
    Проверяет решение студента сравнением
    результата с эталонным SQL-запросом.
    """

    connection = None
    database_path = None

    try:
        exercise_folder = get_exercise_folder(
            exercise_folder
        )

        solution_sql = load_sql_file(
            exercise_folder / "solution.sql"
        )

        connection = create_training_database(
            exercise_folder
        )

        database_path = Path(
            connection.execute("PRAGMA database_list").fetchone()[2]
        )

        configure_query_security(connection)

        # Выполняем запрос студента
        student_result = execute_sql(
            connection,
            student_query
        )

        if not student_result["success"]:
            return {
                "is_correct": False,
                "message": student_result["message"],
                "columns": student_result["columns"],
                "rows": student_result["rows"]
            }

        # Выполняем эталонный запрос
        solution_result = execute_sql(
            connection,
            solution_sql
        )

        if not solution_result["success"]:
            return {
                "is_correct": False,
                "message": "Ошибка эталонного решения",
                "columns": [],
                "rows": []
            }

        # Сравниваем названия столбцов и данные
        is_correct = (
            student_result["columns"]
            == solution_result["columns"]
            and student_result["rows"]
            == solution_result["rows"]
        )

        if is_correct:
            message = "Правильно! Задание выполнено."
        else:
            message = "Результат запроса не совпадает с эталоном."

        return {
            "is_correct": is_correct,
            "message": message,
            "columns": student_result["columns"],
            "rows": student_result["rows"]
        }

    except Exception as error:
        return {
            "is_correct": False,
            "message": str(error),
            "columns": [],
            "rows": []
        }

    finally:
        if connection is not None:
            connection.close()

        if database_path is not None:
            database_path.unlink(missing_ok=True)