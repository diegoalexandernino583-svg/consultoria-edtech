"""Routers modulares FastAPI (auth, usuarios, aprendiz, organizaciones, seguridad, videojuego)."""
from app.routers import auth, usuarios, aprendiz, organizaciones, seguridad, videojuego

__all__ = ["auth", "usuarios", "aprendiz", "organizaciones", "seguridad", "videojuego"]
