"""Root-level Celery worker script for running workers."""

import sys
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.celery_app import celery_app

if __name__ == "__main__":
    # Pass command-line arguments to Celery, default to worker command
    argv = sys.argv[1:] if len(sys.argv) > 1 else ["worker", "--loglevel=info"]
    # On Windows, force solo pool to avoid PermissionError (billiard/prefork not supported)
    if sys.platform == "win32" and "worker" in argv and "--pool" not in " ".join(argv):
        argv = argv + ["--pool=solo"]
    celery_app.worker_main(argv=argv)
