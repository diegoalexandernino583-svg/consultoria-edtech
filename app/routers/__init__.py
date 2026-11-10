"""Routers modulares FastAPI (auth, usuarios, aprendiz, organizaciones, seguridad, videojuego, realtime, webhooks)."""
from app import realtime
from app.routers import auth, usuarios, aprendiz, organizaciones, seguridad, videojuego, webhooks

__all__ = ["auth", "usuarios", "aprendiz", "organizaciones", "seguridad", "videojuego", "realtime", "webhooks"]
