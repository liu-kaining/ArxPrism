"""
ArxPrism - Academic Knowledge Graph Extraction Pipeline

Main FastAPI application entry point.
管理 Neo4j、Redis 连接与关闭的生命周期。

Reference: ARCHITECTURE.md Section 5, TECH_DESIGN.md
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.admin_routes import router as admin_router
from src.api.arxiv_routes import router as arxiv_router
from src.api.me_routes import router as me_router
from src.api.routes import router as api_router
from src.api.task_routes import router as task_router
from src.core.config import settings
from src.database.neo4j_client import neo4j_client
from src.services.task_manager import task_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

_DEV_DOCS = settings.environment.strip().lower() == "development"
_cors_allow_origins = [
    o.strip()
    for o in (settings.cors_origins or "").split(",")
    if o.strip()
]
if not _cors_allow_origins:
    _cors_allow_origins = ["http://localhost:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown:
    - Startup: Initialize Neo4j and Redis connections
    - Shutdown: Close all connections
    """
    # Startup
    logger.info("ArxPrism starting up...")

    # Initialize Neo4j connection with retry logic (max 60 seconds)
    max_retries = 12  # 12 * 5s = 60s
    retry_delay = 5   # seconds
    neo4j_connected = False

    for attempt in range(1, max_retries + 1):
        try:
            await neo4j_client.connect()
            is_connected = await neo4j_client.verify_connectivity()
            if is_connected:
                logger.info("Neo4j connection established")
                neo4j_connected = True
                break
            else:
                logger.warning("Neo4j connection attempt %d/%d failed - could not verify", attempt, max_retries)
        except Exception as e:
            logger.warning("Neo4j connection attempt %d/%d failed: %s", attempt, max_retries, e)

        if attempt < max_retries:
            logger.info("Retrying Neo4j connection in %ds...", retry_delay)
            import asyncio
            await asyncio.sleep(retry_delay)

    if not neo4j_connected:
        logger.error("Neo4j connection failed after all retries - continuing without Neo4j")
        logger.warning("API endpoints requiring Neo4j will return errors")

    # Initialize Redis connection for task manager
    try:
        await task_manager.connect()
        logger.info("Redis connection established for task manager")
    except Exception as e:
        logger.warning("Redis connection failed: %s. Task management may not work properly.", e)

    yield

    # Shutdown
    logger.info("ArxPrism shutting down...")
    await neo4j_client.close()
    await task_manager.close()
    logger.info("Shutdown complete")


app = FastAPI(
    title="ArxPrism",
    description=(
        "Academic knowledge graph extraction pipeline from arXiv papers. "
        "Extracts structured knowledge from SRE/cloud-native papers into Neo4j."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if _DEV_DOCS else None,
    redoc_url="/redoc" if _DEV_DOCS else None,
)

# CORS：显式 Origin 列表，与 allow_credentials 共存时不得使用 "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)
app.include_router(task_router)
app.include_router(arxiv_router)
app.include_router(me_router)
app.include_router(admin_router)


@app.get("/health", tags=["system"])
async def health_check():
    """Public heartbeat endpoint for container healthcheck."""
    return {"status": "ok", "message": "ArxPrism API is running"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    payload = {
        "service": "ArxPrism",
        "version": "0.1.0",
        "description": "Academic knowledge graph extraction pipeline",
    }
    if _DEV_DOCS:
        payload["docs"] = "/docs"
    return payload
