"""
app/routers/videojuego.py
Módulo REST para el Videojuego Educativo de Matemáticas.
Implementa el Diagrama de Secuencia de Acceso y Juego (Escolarizado, Educativo, Vocacional).
"""

from datetime import datetime
import json
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from app import core
from app.cache import cache_service
from app.core import db

logger = logging.getLogger("videojuego.matematicas")
router = APIRouter(prefix="/api/videojuego/matematicas", tags=["Videojuego de Matemáticas"])


class RespuestaItem(BaseModel):
    ejercicio_id: int
    respuesta_seleccionada: str


class EnvioRespuestasPayload(BaseModel):
    usuario_id: int
    nivel: str  # 'escolarizado', 'educativo', 'vocacional'
    tiempo_segundos: int
    respuestas: List[RespuestaItem]


NIVELES_CONFIG = {
    "escolarizado": {
        "nombre": "Escolarizado",
        "subtitulo": "Fundamentos, Conteos y Aritmética Interactiva",
        "descripcion": "Ejercicios visuales de conteo, sumas, restas y series numéricas diseñados para consolidar el pensamiento numérico escolar.",
        "icono": "🎒",
        "color_gradiente": "from-emerald-500 to-teal-700",
        "vidas": 3,
        "tiempo_total_segundos": 180,
        "puntos_base": 100,
        "guia": [
            "Observa con atención cada conteo o problema escolar.",
            "Selecciona la opción correcta antes de que expire el tiempo.",
            "Cuentas con 3 vidas para completar la ronda de ejercicios.",
            "Al acertar consecutivamente desbloquearás estrellas y medallas de racha."
        ]
    },
    "educativo": {
        "nombre": "Educativo",
        "subtitulo": "Resolución de Problemas, Fracciones y Razonamiento",
        "descripcion": "Desafíos contextualizados en situaciones reales: porcentajes, proporciones, geometría básica y análisis cuantitativo.",
        "icono": "📐",
        "color_gradiente": "from-sky-500 to-indigo-700",
        "vidas": 3,
        "tiempo_total_segundos": 240,
        "puntos_base": 150,
        "guia": [
            "Lee detenidamente el contexto del problema educativo.",
            "Aplica razonamiento de proporciones, porcentajes o fracciones.",
            "Cada respuesta acertada sumará experiencia pedagógica a tu perfil.",
            "Recibirás retroalimentación explicativa paso a paso al finalizar."
        ]
    },
    "vocacional": {
        "nombre": "Vocacional",
        "subtitulo": "Matemática Aplicada, Finanzas y Lógica de Negocios",
        "descripcion": "Problemas de toma de decisiones vocacionales: análisis de costos, punto de equilibrio, lógica algorítmica y razonamiento crítico.",
        "icono": "💼",
        "color_gradiente": "from-purple-500 to-pink-700",
        "vidas": 3,
        "tiempo_total_segundos": 300,
        "puntos_base": 200,
        "guia": [
            "Examina indicadores clave, presupuestos y modelos lógicos.",
            "Determina la decisión matemática óptima para cada caso vocacional.",
            "Obtén el máximo puntaje para rankearte en el Cuadro de Honor estudiantil.",
            "Desbloquea insignias de excelencia analítica institucional."
        ]
    }
}


@router.get("/niveles")
def obtener_niveles_disponibles(usuario_id: Optional[int] = None):
    """
    Retorna la configuración de los 3 niveles con el mejor puntaje del estudiante si está autenticado.
    """
    resultados = []
    for nivel_key, cfg in NIVELES_CONFIG.items():
        mejor_puntaje = 0
        partidas_jugadas = 0

        if usuario_id:
            prog = db.execute_query("""
                SELECT MAX(puntaje_obtenido) as mejor_score, COUNT(id) as total_partidas
                FROM progreso_videojuego_matematicas
                WHERE usuario_id = ? AND nivel = ?
            """, (usuario_id, nivel_key), fetchone=True)
            if prog:
                mejor_puntaje = prog.get("mejor_score") or 0
                partidas_jugadas = prog.get("total_partidas") or 0

        resultados.append({
            "id": nivel_key,
            "nombre": cfg["nombre"],
            "subtitulo": cfg["subtitulo"],
            "descripcion": cfg["descripcion"],
            "icono": cfg["icono"],
            "color": cfg["color_gradiente"],
            "vidas": cfg["vidas"],
            "tiempo_segundos": cfg["tiempo_total_segundos"],
            "mejor_puntaje": mejor_puntaje,
            "partidas_jugadas": partidas_jugadas
        })

    return {"status": "success", "niveles": resultados}


@router.get("/nivel/{nivel}")
def solicitar_contenido_nivel(nivel: str, usuario_id: Optional[int] = None):
    """
    Paso 2-5 del Diagrama de Secuencia:
    Solicita y retorna ejercicios, recursos pedagógicos y configuración interactiva del nivel seleccionado.
    """
    nivel = nivel.lower().strip()
    if nivel not in NIVELES_CONFIG:
        raise HTTPException(status_code=400, detail=f"Nivel '{nivel}' no válido. Opciones: escolarizado, educativo, vocacional.")

    cfg = NIVELES_CONFIG[nivel]

    # Consultar ejercicios activos en Base de Datos
    ejercicios_db = db.execute_query("""
        SELECT id, nivel, categoria, titulo, enunciado, imagen_o_icono, opciones_json, puntos, tiempo_limite_segundos
        FROM videojuego_matematicas_ejercicios
        WHERE nivel = ? AND activo = 1
        ORDER BY id ASC
    """, (nivel,), fetchall=True) or []

    lista_ejercicios = []
    for row in ejercicios_db:
        opciones = []
        try:
            opciones = json.loads(row.get("opciones_json") or "[]")
        except Exception:
            opciones = []

        lista_ejercicios.append({
            "id": row.get("id"),
            "categoria": row.get("categoria"),
            "titulo": row.get("titulo"),
            "enunciado": row.get("enunciado"),
            "icono": row.get("imagen_o_icono") or cfg["icono"],
            "opciones": opciones,
            "puntos": row.get("puntos") or cfg["puntos_base"],
            "tiempo_segundos": row.get("tiempo_limite_segundos") or 60
        })

    return {
        "status": "success",
        "nivel": nivel,
        "configuracion": {
            "nombre": cfg["nombre"],
            "subtitulo": cfg["subtitulo"],
            "icono": cfg["icono"],
            "vidas": cfg["vidas"],
            "tiempo_total_segundos": cfg["tiempo_total_segundos"],
            "guia_usuario": cfg["guia"]
        },
        "total_ejercicios": len(lista_ejercicios),
        "ejercicios": lista_ejercicios
    }


@router.post("/evaluar")
def evaluar_respuestas_y_registrar(payload: EnvioRespuestasPayload):
    """
    Pasos 8-11 del Diagrama de Secuencia:
    Recibe respuestas del estudiante, evalúa aciertos, persiste puntaje y progreso en BD,
    y retorna feedback pedagógico y recompensas visuales (estrellas, medallas).
    """
    nivel = payload.nivel.lower().strip()
    if nivel not in NIVELES_CONFIG:
        raise HTTPException(status_code=400, detail="Nivel de videojuego no válido.")

    cfg = NIVELES_CONFIG[nivel]

    # Consultar respuestas correctas y explicaciones desde la BD
    ejercicios_db = db.execute_query("""
        SELECT id, titulo, respuesta_correcta, explicacion, puntos
        FROM videojuego_matematicas_ejercicios
        WHERE nivel = ? AND activo = 1
    """, (nivel,), fetchall=True) or []

    mapa_correctas = {e["id"]: e for e in ejercicios_db}
    total_ejercicios = len(mapa_correctas)
    if total_ejercicios == 0:
        total_ejercicios = max(1, len(payload.respuestas))

    aciertos = 0
    desglose_resultados = []
    puntaje_total = 0

    for resp in payload.respuestas:
        ej_id = resp.ejercicio_id
        sel = resp.respuesta_seleccionada.strip()

        if ej_id in mapa_correctas:
            esperada = str(mapa_correctas[ej_id]["respuesta_correcta"]).strip()
            es_correcta = (sel.lower() == esperada.lower())
            puntos_ej = mapa_correctas[ej_id]["puntos"] if es_correcta else 0

            if es_correcta:
                aciertos += 1
                puntaje_total += puntos_ej

            desglose_resultados.append({
                "ejercicio_id": ej_id,
                "titulo": mapa_correctas[ej_id]["titulo"],
                "respuesta_seleccionada": sel,
                "es_correcta": es_correcta,
                "respuesta_correcta": esperada,
                "explicacion": mapa_correctas[ej_id]["explicacion"],
                "puntos_ganados": puntos_ej
            })

    porcentaje_acierto = round((aciertos / max(1, total_ejercicios)) * 100, 1)

    # Determinación de estrellas y feedback pedagógico
    estrellas = 1
    if porcentaje_acierto >= 90:
        estrellas = 3
        tipo_feedback = "EXCELENCIA"
        mensaje_feedback = f"¡Extraordinario desempeño! Has dominado el nivel {cfg['nombre']} con maestría matemática."
        medalla = "🥇 Medalla de Oro en Pensamiento Matemático"
    elif porcentaje_acierto >= 60:
        estrellas = 2
        tipo_feedback = "APROBADO"
        mensaje_feedback = f"¡Buen trabajo! Has completado con éxito la actividad de nivel {cfg['nombre']}. Sigue practicando para alcanzar la perfección."
        medalla = "🥈 Medalla de Plata en Razonamiento Cuantitativo"
    else:
        estrellas = 1
        tipo_feedback = "APOYO_PEDAGOGICO"
        mensaje_feedback = f"¡Ánimo! El aprendizaje es un proceso continuo. Revisa las explicaciones de cada ejercicio y vuelve a intentarlo para superar tu récord."
        medalla = "🥉 Insignia de Esfuerzo & Dedicación"

    recompensas = {
        "estrellas": estrellas,
        "medalla": medalla,
        "puntos_experiencia": puntaje_total,
        "porcentaje_acierto": porcentaje_acierto,
        "tiempo_empleado_segundos": payload.tiempo_segundos
    }

    # Obtener organizacion_id del usuario
    usuario = db.execute_query("SELECT organizacion_id, nombre FROM usuarios WHERE id = ?", (payload.usuario_id,), fetchone=True)
    org_id = usuario.get("organizacion_id") if usuario else 1

    # Registrar en Base de Datos (Paso 9 y 10 del diagrama de secuencia)
    progreso_id = db.execute_query("""
        INSERT INTO progreso_videojuego_matematicas
        (usuario_id, organizacion_id, nivel, puntaje_obtenido, aciertos, total_preguntas, tiempo_empleado_segundos, recompensas_json, feedback_mensaje, fecha_registro)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        payload.usuario_id,
        org_id,
        nivel,
        puntaje_total,
        aciertos,
        total_ejercicios,
        payload.tiempo_segundos,
        json.dumps(recompensas, ensure_ascii=False),
        mensaje_feedback,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ), commit=True, return_id=True)

    # Bonificación: Actualizar minutos dedicados y racha en el perfil del usuario
    minutos_ganados = max(5, payload.tiempo_segundos // 60)
    try:
        db.execute_query("""
            UPDATE usuarios
            SET minutos_dedicados_totales = COALESCE(minutos_dedicados_totales, 0) + ?
            WHERE id = ?
        """, (minutos_ganados, payload.usuario_id), commit=True)
    except Exception:
        pass

    # Invalidar caché del tenant para que los rankings reflejen el nuevo puntaje
    if org_id:
        cache_service.invalidar_tenant(str(org_id))

    return {
        "status": "success",
        "progreso_id": progreso_id,
        "resumen": {
            "nivel": nivel,
            "nombre_nivel": cfg["nombre"],
            "puntaje_total": puntaje_total,
            "aciertos": aciertos,
            "total_ejercicios": total_ejercicios,
            "porcentaje_acierto": porcentaje_acierto,
            "tiempo_segundos": payload.tiempo_segundos
        },
        "recompensas": recompensas,
        "feedback": {
            "tipo": tipo_feedback,
            "mensaje": mensaje_feedback,
            "medalla": medalla,
            "estrellas": estrellas
        },
        "desglose": desglose_resultados
    }


@router.get("/historial/{usuario_id}")
def obtener_historial_estudiante(usuario_id: int):
    """
    Retorna el historial de partidas, medallas y puntajes del estudiante en el videojuego de matemáticas.
    """
    historial = db.execute_query("""
        SELECT id, nivel, puntaje_obtenido, aciertos, total_preguntas, tiempo_empleado_segundos, recompensas_json, feedback_mensaje, fecha_registro
        FROM progreso_videojuego_matematicas
        WHERE usuario_id = ?
        ORDER BY id DESC
        LIMIT 20
    """, (usuario_id,), fetchall=True) or []

    stats = db.execute_query("""
        SELECT COUNT(id) as total_partidas,
               COALESCE(SUM(puntaje_obtenido), 0) as puntos_acumulados,
               COALESCE(MAX(puntaje_obtenido), 0) as record_maximo,
               COALESCE(SUM(aciertos), 0) as aciertos_totales
        FROM progreso_videojuego_matematicas
        WHERE usuario_id = ?
    """, (usuario_id,), fetchone=True) or {}

    return {
        "status": "success",
        "estadisticas": stats,
        "historial": historial
    }
