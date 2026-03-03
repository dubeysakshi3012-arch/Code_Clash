"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.api.v1 import auth, assessment, health, submission, matches

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="CodeClash API - Assessment-based onboarding with ELO progression",
    docs_url="/docs",
    redoc_url="/redoc"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
cors_origins = settings.get_cors_origins()
print(f"CORS origins configured: {cors_origins}")  # Debug logging
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(assessment.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")
app.include_router(submission.router, prefix="/api/v1")
app.include_router(matches.router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    # TODO: Initialize Redis connection if needed
    # TODO: Initialize Docker client if needed
    pass


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    # TODO: Close Redis connection if needed
    # TODO: Close Docker client if needed
    pass


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to CodeClash API",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }
