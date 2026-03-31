"""
ArxPrism - Academic Knowledge Graph Extraction Pipeline

Main FastAPI application entry point.
管理 Neo4j 连接与关闭的生命周期。

Reference: ARCHITECTURE.md Section 5, TECH_DESIGN.md
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router as api_router
from src.core.config import settings
from src.database.neo4j_client import neo4j_client

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
    - Startup: Initialize Neo4j connection with retry (max 60s)
    - Shutdown: Close Neo4j connection
    """
    # Startup
    logger.info("ArxPrism starting up...")

    # Initialize Neo4j connection with retry logic (max 60 seconds)
    max_retries = 12  # 12 * 5s = 60s
    retry_delay = 5   # seconds
    connected = False

    for attempt in range(1, max_retries + 1):
        try:
            await neo4j_client.connect()
            is_connected = await neo4j_client.verify_connectivity()
            if is_connected:
                logger.info("Neo4j connection established")
                connected = True
                break
            else:
                logger.warning(f"Neo4j connection attempt {attempt}/{max_retries} failed - could not verify")
        except Exception as e:
            logger.warning(f"Neo4j connection attempt {attempt}/{max_retries} failed: {e}")

        if attempt < max_retries:
            logger.info(f"Retrying Neo4j connection in {retry_delay}s...")
            import asyncio
            await asyncio.sleep(retry_delay)

    if not connected:
        logger.error("Neo4j connection failed after all retries - continuing without Neo4j")
        logger.warning("API endpoints requiring Neo4j will return errors")

    yield

    # Shutdown
    logger.info("ArxPrism shutting down...")
    await neo4j_client.close()
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "arxprism"}


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "ArxPrism",
        "version": "0.1.0",
        "description": "Academic knowledge graph extraction pipeline",
        "docs": "/docs"
    }
