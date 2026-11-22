from fastapi import FastAPI
from back.config import settings
from back.api import router


app = FastAPI(
    title=settings.app_name,
    description="Backend API для обучающей платформы SQL Trainer",
    version="1.0.0",
)


app.include_router(router)



@app.get("/", tags=["Система"])
def root():
    """
    Проверяет доступность Backend.
    """

    return {
        "success": True,
        "message": "SQL Trainer Backend работает"
    }


@app.get("/health", tags=["Система"])
def health_check():
    """
    Проверяет состояние Backend.
    """

    return {
        "status": "healthy"
    }
