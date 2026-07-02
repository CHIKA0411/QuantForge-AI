import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import get_db, SessionLocal
from app.config import settings
from app.collector import start_collector, stop_collector
from app.routes import market, analytics, signals

logger = logging.getLogger("quantforge.main")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events to manage background schedulers and databases."""
    logger.info("Initializing QuantForge AI Services...")
    # Start the background option chain collector scheduler
    start_collector()
    yield
    # Stop background scheduler
    logger.info("Shutting down QuantForge AI Services...")
    stop_collector()

app = FastAPI(
    title="QuantForge AI Backend API",
    description="Institutional-Grade Options Intelligence & Quantitative Research API",
    version="1.0",
    lifespan=lifespan
)

# CORS Policy configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(market.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(signals.router, prefix="/api")

@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """Health check validating application state and database connection connectivity."""
    db_status = "healthy"
    db_engine = "Unknown"
    
    try:
        # Check connection
        db.execute(text("SELECT 1"))
        
        # Identify engine type
        from app import db as db_module
        db_engine = "PostgreSQL" if db_module.is_postgres else "SQLite (Fallback)"
    except Exception as e:
        logger.error(f"Health check database connection failure: {e}")
        db_status = f"unhealthy ({e})"
        
    return {
        "status": "healthy",
        "database": db_status,
        "database_type": db_engine,
        "environment": settings.APP_ENV,
        "simulation_mode": settings.NSE_SIMULATE
    }
