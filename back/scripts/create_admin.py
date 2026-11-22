import getpass
from pydantic import ValidationError
from sqlalchemy import select
from back.database import SessionLocal
from back.models import User
from back.schemas import UserRegister
from back.security import hash_password


def create_admin():
    """
    Создаёт администратора SQL-Trainer.
    """

    print("=" * 45)
    print("Создание администратора SQL-Trainer")
    print("=" * 45)

    email = input("Введите Email администратора: ").strip()
    password = getpass.getpass("Введите пароль: ")
    password_confirmation = getpass.getpass("Повторите пароль: ")

    if password != password_confirmation:
        print("Ошибка: пароли не совпадают.")
        return

    try:
        user_data = UserRegister(
            email=email,
            password=password,
        )
    except ValidationError as error:
        print("Ошибка: введены некорректные данные.")
        print(error)
        return

    db = SessionLocal()

    try:
        existing_user = db.scalar(
            select(User).where(User.email == user_data.email)
        )

        if existing_user:
            print("Ошибка: пользователь с таким Email уже существует.")
            return

        admin = User(
            email=user_data.email,
            password_hash=hash_password(user_data.password),
            role="admin",
            is_active=True,
        )

        db.add(admin)
        db.commit()

        print()
        print("Администратор успешно создан!")
        print(f"Email: {admin.email}")
        print(f"Роль: {admin.role}")

    except Exception as error:
        db.rollback()
        print(f"Не удалось создать администратора: {error}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
