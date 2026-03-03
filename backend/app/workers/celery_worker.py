"""Celery worker entry point."""

import logging
from app.core.celery_app import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Export celery_app for use with celery CLI
__all__ = ['celery_app']
