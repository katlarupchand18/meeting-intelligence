from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.accountability import router as accountability_router
from app.api.analysis import router as analysis_router
from app.api.commitments import router as commitments_router
from app.api.decisions import router as decisions_router
from app.api.evidence import router as evidence_router
from app.api.memory import router as memory_router
from app.api.meetings import router as meetings_router
from app.api.participants import router as participants_router
from app.api.transcription import router as transcription_router

from app.core.config import settings


# =========================================================
# APPLICATION LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    upload_dir = Path(
        settings.UPLOAD_DIR
    )

    upload_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 70)
    print(
        "Meeting Intelligence & Accountability System"
    )
    print("=" * 70)

    print(
        f"Environment: {settings.APP_ENV}"
    )

    print(
        f"Upload directory: "
        f"{upload_dir.resolve()}"
    )

    print(
        f"CORS origins: "
        f"{settings.cors_origins_list}"
    )

    print("=" * 70)

    yield

    print(
        "Meeting Intelligence backend shutting down..."
    )


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered Meeting Intelligence & "
        "Accountability System for transcription, "
        "speaker identification, summaries, "
        "decisions, commitments, evidence, "
        "cross-meeting memory, participant "
        "intelligence, and accountability tracking."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# API ROUTES
# =========================================================

app.include_router(
    meetings_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    transcription_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    analysis_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    commitments_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    decisions_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    evidence_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    memory_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    accountability_router,
    prefix=settings.API_V1_PREFIX,
)

app.include_router(
    participants_router,
    prefix=settings.API_V1_PREFIX,
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():

    return {
        "success": True,
        "application": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "message": (
            "Meeting Intelligence backend "
            "is running."
        ),
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
async def health_check():

    return {
        "success": True,
        "status": "healthy",
        "service": (
            "meeting-intelligence-backend"
        ),
    }


# =========================================================
# API INFORMATION
# =========================================================

@app.get("/api")
async def api_info():

    prefix = settings.API_V1_PREFIX

    return {
        "success": True,
        "name": settings.APP_NAME,
        "version": "1.0.0",

        "modules": {
            "meetings":
                f"{prefix}/meetings",

            "transcription":
                f"{prefix}/transcription",

            "analysis":
                f"{prefix}/analysis",

            "commitments":
                f"{prefix}/commitments",

            "decisions":
                f"{prefix}/decisions",

            "evidence":
                f"{prefix}/evidence",

            "memory":
                f"{prefix}/memory",

            "accountability":
                f"{prefix}/accountability",

            "participants":
                f"{prefix}/participants",
        },
    }