#!/usr/bin/env python3
"""
Главное FastAPI приложение для веб-платформы анализатора
Архитектура: PostgreSQL + Redis + FastAPI + Modern HTML/CSS/JS Frontend
"""

import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime
import logging

# Импорты внутренних модулей
from core.config import get_settings
from core.database import init_db, close_db, get_db_health, get_table_stats
from core.redis_client import init_redis, close_redis, get_redis_health
from api.v1.main import api_router

# Настройка логирования
logger = logging.getLogger(__name__)

# Получаем настройки приложения
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом приложения
    """
    # Startup
    print("🚀 Запуск веб-платформы анализатора...")
    
    # Инициализация базы данных
    try:
        print("🔍 [DEBUG] Инициализируем соединение с БД...")
        await init_db()
        print("✅ База данных PostgreSQL инициализирована")
        
        # Проверяем здоровье БД
        print("🔍 [DEBUG] Проверяем соединение с БД...")
        db_health = await get_db_health()
        print(f"🔍 [DEBUG] Статус БД: {'✅ Здоровая' if db_health else '❌ Недоступна'}")
        
        # Проверяем таблицы в БД
        try:
            table_stats = await get_table_stats()
            print(f"🔍 [DEBUG] Статистика таблиц БД: {table_stats}")
        except Exception as table_error:
            print(f"⚠️ [DEBUG] Не удалось получить статистику таблиц: {table_error}")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        print(f"🔍 [DEBUG] Тип ошибки БД: {type(e)}")
        import traceback
        print(f"🔍 [DEBUG] Трейс ошибки БД: {traceback.format_exc()}")
        raise
    
    # Инициализация Redis
    try:
        print("🔍 [DEBUG] Инициализируем соединение с Redis...")
        await init_redis()
        print("✅ Redis кэш инициализирован")
        
        # Проверяем здоровье Redis
        print("🔍 [DEBUG] Проверяем соединение с Redis...")
        redis_health = await get_redis_health()
        print(f"🔍 [DEBUG] Статус Redis: {'✅ Здоровый' if redis_health else '❌ Недоступен'}")
        
    except Exception as e:
        print(f"❌ Ошибка инициализации Redis: {e}")
        print(f"🔍 [DEBUG] Тип ошибки Redis: {type(e)}")
        import traceback
        print(f"🔍 [DEBUG] Трейс ошибки Redis: {traceback.format_exc()}")
        raise
    
    print("🎉 Веб-платформа анализатора запущена успешно!")
    
    yield
    
    # Shutdown
    print("🛑 Остановка веб-платформы анализатора...")
    
    try:
        await close_redis()
        print("✅ Redis соединение закрыто")
    except Exception as e:
        print(f"❌ Ошибка закрытия Redis: {e}")
    
    try:
        await close_db()
        print("✅ БД соединение закрыто")
    except Exception as e:
        print(f"❌ Ошибка закрытия БД: {e}")
    
    print("👋 Веб-платформа анализатора остановлена")


def create_application() -> FastAPI:
    """
    Фабрика приложения FastAPI с лучшими практиками
    """
    # Создание приложения FastAPI
    app = FastAPI(
        title="Analyzer Platform",
        description="Веб-платформа для анализа системы с поддержкой HTML отчетов",
        version="v0.0.1",
        docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
        openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
        # Теги для группировки endpoints
        tags_metadata=[
            {
                "name": "reports",
                "description": "Управление отчетами анализатора",
            },
            {
                "name": "analytics",
                "description": "Аналитика и статистика",
            },
            {
                "name": "upload",
                "description": "Загрузка файлов отчетов",
            },
            {
                "name": "health",
                "description": "Проверка здоровья системы",
            },
        ]
    )
    
    # Настройка CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    # Middleware для сжатия
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Middleware для доверенных хостов
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )
    
    # Подключение API роутеров
    app.include_router(
        api_router,
        prefix="/api/v1"
    )
    
    # Статические файлы (для загруженных отчетов)
    if os.path.exists("uploads"):
        app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
    
    # Статические файлы frontend
    frontend_path = "../frontend"
    if os.path.exists(frontend_path):
        # Подключаем статические ресурсы (CSS, JS)
        if os.path.exists(os.path.join(frontend_path, "css")):
            app.mount("/css", StaticFiles(directory=os.path.join(frontend_path, "css")), name="css")
        if os.path.exists(os.path.join(frontend_path, "js")):
            app.mount("/js", StaticFiles(directory=os.path.join(frontend_path, "js")), name="js")
        
        # Главная страница
        @app.get("/", include_in_schema=False)
        async def serve_frontend():
            return FileResponse(os.path.join(frontend_path, "index.html"))
    
    # Статические файлы frontend (в production)
    elif settings.ENVIRONMENT == "production" and os.path.exists("../frontend/dist"):
        app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="frontend")
    
    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check():
        """
        Проверка здоровья всех сервисов
        """
        db_status = await get_db_health()
        redis_status = await get_redis_health()
        
        status = "healthy" if db_status and redis_status else "unhealthy"
        
        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": "healthy" if db_status else "unhealthy",
                "redis": "healthy" if redis_status else "unhealthy"
            }
        }
    
    # App info endpoint
    @app.get("/api/v1/app/info", tags=["app"])
    async def get_app_info():
        """
        Получение информации о приложении
        """
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "description": "Веб-платформа для анализа системы с поддержкой HTML отчетов"
        }
    
    # Middleware для логирования запросов
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = datetime.utcnow()
        
        # Логируем запрос
        print(f"📥 {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Вычисляем время обработки
        process_time = (datetime.utcnow() - start_time).total_seconds()
        response.headers["X-Process-Time"] = str(process_time)
        
        # Логируем ответ
        print(f"📤 {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)")
        
        return response
    
    return app


# Создаем экземпляр приложения
app = create_application()


if __name__ == "__main__":
    """
    Запуск для разработки
    """
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
        reload_dirs=["./"],
        reload_excludes=["*.pyc", "*.pyo", "__pycache__"]
    ) 