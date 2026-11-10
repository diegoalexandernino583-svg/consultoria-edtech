"""Routers modulares FastAPI (auth, usuarios, aprendiz, organizaciones, seguridad, videojuego, realtime)."""
from app import realtime
from app.routers import auth, usuarios, aprendiz, organizaciones, seguridad, videojuego

__all__ = ["auth", "usuarios", "aprendiz", "organizaciones", "seguridad", "videojuego", "realtime"]
