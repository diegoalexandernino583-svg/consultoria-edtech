"""Alias de entrada estándar FastAPI (`uvicorn main:app` / `uvicorn app_visual:app`)."""
from app_visual import app

__all__ = ["app"]
