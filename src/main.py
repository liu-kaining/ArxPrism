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
                logger.warning(f"Neo4j connection attempt {attempt}/{max_retries} failed - could not verify")
        except Exception as e:
            logger.warning(f"Neo4j connection attempt {attempt}/{max_retries} failed: {e}")

        if attempt < max_retries:
            logger.info(f"Retrying Neo4j connection in {retry_delay}s...")
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
        logger.warning(f"Redis connection failed: {e}. Task management may not work properly.")

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
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    return {
        "service": "ArxPrism",
        "version": "0.1.0",
        "description": "Academic knowledge graph extraction pipeline",
        "docs": "/docs"
    }
