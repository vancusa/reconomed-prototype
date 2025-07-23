"""ReconoMed FastAPI Application - Main Entry Point"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import os

from app.database import get_db, create_tables
from app.routers.patients import router as patients_router
from app.routers.documents import router as documents_router
from app.routers.search import router as search_router

# Create FastAPI app
app = FastAPI(
    title="ReconoMed API",
    description="Healthcare Document Processing Platform",
    version="0.1.0"
)

# Create upload directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(patients_router)
app.include_router(documents_router)
app.include_router(search_router)

# Create database tables on startup
@app.on_event("startup")
def startup_event():
    create_tables()

# Serve the frontend
@app.get("/")
def serve_frontend():
    return FileResponse('static/index.html')

# Serve the login page
@app.get("/login")
def serve_login():
    return FileResponse('static/login.html')

# Health check endpoints
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "ReconoMed API"}

# Test database connection
@app.get("/test-db")
def test_database(db: Session = Depends(get_db)):
    """Test database connection"""
    try:
        # Simple query to test connection
        result = db.execute(text("SELECT 1 as test")).fetchone()
        return {"database": "connected", "test_query": result[0]}
    except Exception as e:
        return {"database": "error", "message": str(e)}