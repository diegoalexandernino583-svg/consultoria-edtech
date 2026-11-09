"""
app/cache.py
Servicio de Caché Distribuido con Aislamiento Estricto por Tenant.
Compatible con Redis y con fallback transparente en memoria para alta concurrencia.
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger("cache.service")


class TenantCacheService:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.redis_client = None
        self._memory_cache = {}
        self._memory_ttl = {}

        if self.redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                self.redis_client.ping()
                logger.info(">> [CACHE] Conectado exitosamente a Redis distribuido.")
            except Exception as e:
                logger.warning(f">> [CACHE] Redis no disponible ({e}). Activando fallback en memoria.")
                self.redis_client = None

    def _generar_clave(self, tenant_id: str, namespace: str, params: dict) -> str:
        serialized = json.dumps(params, sort_keys=True, default=str)
        h = hashlib.sha256(serialized.encode()).hexdigest()[:16]
        return f"tenant:{tenant_id}:{namespace}:{h}"

    def get(self, tenant_id: str, namespace: str, params: dict) -> Optional[Any]:
        clave = self._generar_clave(tenant_id, namespace, params)
        if self.redis_client:
            try:
                data = self.redis_client.get(clave)
                return json.loads(data) if data else None
            except Exception:
                pass

        # Fallback en memoria
        if clave in self._memory_cache:
            if time.time() < self._memory_ttl.get(clave, 0):
                return self._memory_cache[clave]
            else:
                del self._memory_cache[clave]
                self._memory_ttl.pop(clave, None)
        return None

    def set(self, tenant_id: str, namespace: str, params: dict, valor: Any, ttl_segundos: int = 300):
        clave = self._generar_clave(tenant_id, namespace, params)
        if self.redis_client:
            try:
                self.redis_client.setex(clave, ttl_segundos, json.dumps(valor, default=str))
                return
            except Exception:
                pass

        # Fallback en memoria
        self._memory_cache[clave] = valor
        self._memory_ttl[clave] = time.time() + ttl_segundos

    def invalidar_tenant(self, tenant_id: str):
        if self.redis_client:
            try:
                keys = self.redis_client.keys(f"tenant:{tenant_id}:*")
                if keys:
                    self.redis_client.delete(*keys)
            except Exception:
                pass

        prefix = f"tenant:{tenant_id}:"
        claves_a_borrar = [k for k in self._memory_cache.keys() if k.startswith(prefix)]
        for k in claves_a_borrar:
            self._memory_cache.pop(k, None)
            self._memory_ttl.pop(k, None)


# Instancia singleton accesible globalmente
cache_service = TenantCacheService()
