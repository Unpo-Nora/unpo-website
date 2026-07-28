from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from .database import get_db
from .routers import products, leads, auth, analytics, sales, settings
import logging
import os

logger = logging.getLogger("uvicorn.error")

# El esquema PostgreSQL lo gestiona EXCLUSIVAMENTE Alembic (baseline 71e9e987f7d2).
# El arranque NO ejecuta DDL: nada de Base.metadata.create_all() ni `alembic upgrade`.

app = FastAPI(
    title="UNPO & NORA Ecosystem API",
    description="Backend unificado para B2B y B2C",
    version="1.0.0"
)

# CORS Configuration
env_origins = os.getenv("CORS_ORIGINS")
if env_origins:
    origins = [orig.strip() for orig in env_origins.split(",") if orig.strip()]
else:
    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "https://unpo.com.ar",
        "https://www.unpo.com.ar",
        "https://unpo.online",
        "https://www.unpo.online",
        "https://unpo-website.vercel.app"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers — production-safe: log details server-side (traceback via
# logger.exception) and return a generic message. NEVER leak stack traces to the client.
@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request, exc):
    logger.error("ResponseValidationError on %s: %s", request.url.path, exc.errors())
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.include_router(products.router)
app.include_router(leads.router)
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(sales.router)
app.include_router(settings.router)
from .routers import users, hr, finance, whatsapp, whatsapp_inbox
app.include_router(users.router)
app.include_router(hr.router)
app.include_router(finance.router)
# Webhook de WhatsApp Cloud API (público: la autenticación es la firma de Meta).
app.include_router(whatsapp.router)
# Inbox multiagente de WhatsApp (autenticado: JWT + autorización por usuario y línea).
app.include_router(whatsapp_inbox.router)

# Mount static images and videos
images_path = "data/images"
videos_path = "data/videos"
os.makedirs(images_path, exist_ok=True)
os.makedirs(videos_path, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=images_path), name="static_images")
app.mount("/static/videos", StaticFiles(directory=videos_path), name="static_videos")


@app.get("/")
def read_root():
    return {"status": "online", "system": "UNPO/NORA Ecosystem API"}


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Liveness/readiness probe para ALB/ECS. Ejecuta `SELECT 1` contra la DB.
    - DB responde  -> HTTP 200 {"status": "ok", "db": "connected"}
    - DB falla     -> HTTP 503 {"status": "error", "db": "disconnected"}
    No expone stacktrace al cliente (se loguea server-side).
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        logger.exception("Health check DB error")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "db": "disconnected"},
        )
