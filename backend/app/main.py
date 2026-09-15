"""
FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload --port 8000   (from backend/)
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.api.webhooks import router as webhooks_router
from app.database.base import init_db
from app.utils.logging_setup import configure_logging

configure_logging(level=logging.INFO)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("app.startup_complete")
    yield


app = FastAPI(
    title="Agentic AI Code Reviewer",
    description="Automated, agentic PR review backend.",
    version="0.1.0",
    lifespan=lifespan,
)

# Local dev only -- tighten this before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(webhooks_router)

