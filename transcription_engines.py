# -*- coding: utf-8 -*-
"""transcription_engines.py — Registro y seleccion de motores de transcripcion.

Modulo extraido de audioclass_v91.py. Contiene el diccionario de
motores de transcripcion disponibles y la logica de seleccion
basada en configuracion del usuario.

Uso:
    from transcription_engines import TRANSCRIPTION_ENGINES, select_engine
    engine = select_engine(config)
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptionEngine:
    """Define un motor de transcripcion disponible.

    Attributes:
        name: Nombre legible del motor (ej: 'Local (faster-whisper)').
        key: Clave interna para la config (ej: 'local', 'gemini').
        requires_key: True si necesita API key para funcionar.
        requires_url: True si necesita URL de servidor (ej: Colab).
        description: Descripcion corta para el usuario.
    """
    name: str
    key: str
    requires_key: bool = False
    requires_url: bool = False
    description: str = ""


# ── Registro de motores ───────────────────────────────────────────────────
# Cada entrada es un TranscriptionEngine que la UI puede presentar
# en un selector/dropdown. La clave del dict es el identificador interno.

TRANSCRIPTION_ENGINES = {
    "local": TranscriptionEngine(
        name="Local (faster-whisper)",
        key="local",
        requires_key=False,
        description="Transcripcion offline con modelos Tiny/Base/Small. Sin internet."
    ),
    "local_whisper": TranscriptionEngine(
        name="Local (openai-whisper)",
        key="local_whisper",
        requires_key=False,
        description="Transcripcion offline con openai-whisper. Mas lento que faster-whisper."
    ),
    "gemini": TranscriptionEngine(
        name="Gemini (Google AI)",
        key="gemini",
        requires_key=True,
        description="Transcripcion remota via Google Gemini. Rapido y preciso."
    ),
    "openai": TranscriptionEngine(
        name="OpenAI (GPT)",
        key="openai",
        requires_key=True,
        description="Transcripcion remota via OpenAI API. Alta calidad."
    ),
    "colab": TranscriptionEngine(
        name="Colab (GPU remota)",
        key="colab",
        requires_key=False,
        requires_url=True,
        description="Transcripcion via Google Colab con GPU. Requiere URL del servidor."
    ),
}


def select_engine(config):
    """Selecciona el motor de transcripcion basado en la configuracion.

    Args:
        config: Dict de configuracion con 'mode', 'gemini_api_key',
                'openai_api_key', 'colab_url', etc.

    Returns:
        Tupla (engine_key, engine_info) o (None, None) si no hay motor.
    """
    mode = config.get("mode", "local")

    if mode == "local":
        return "local", TRANSCRIPTION_ENGINES["local"]
    elif mode == "local_whisper":
        return "local_whisper", TRANSCRIPTION_ENGINES["local_whisper"]
    elif mode == "gemini":
        if config.get("gemini_api_key"):
            return "gemini", TRANSCRIPTION_ENGINES["gemini"]
        return None, None
    elif mode == "openai":
        if config.get("openai_api_key"):
            return "openai", TRANSCRIPTION_ENGINES["openai"]
        return None, None
    elif mode == "cloud":
        if config.get("colab_url"):
            return "colab", TRANSCRIPTION_ENGINES["colab"]
        return None, None

    # Fallback: intentar local
    return "local", TRANSCRIPTION_ENGINES["local"]


def get_available_engines(config):
    """Devuelve la lista de motores disponibles segun la config.

    Args:
        config: Dict de configuracion.

    Returns:
        Lista de tuplas (key, engine, available) donde available indica
        si el motor puede usarse (tiene API key si la necesita).
    """
    result = []
    for key, engine in TRANSCRIPTION_ENGINES.items():
        available = True
        if engine.requires_key:
            if key == "gemini":
                available = bool(config.get("gemini_api_key"))
            elif key == "openai":
                available = bool(config.get("openai_api_key"))
        if engine.requires_url:
            available = bool(config.get("colab_url"))
        result.append((key, engine, available))
    return result


def engine_status_text(config):
    """Devuelve un texto descriptivo del motor actual y su estado.

    Args:
        config: Dict de configuracion.

    Returns:
        str con el nombre del motor y si esta listo.
    """
    key, engine = select_engine(config)
    if engine is None:
        return "Sin motor configurado"
    status = "listo" if key else "falta configuracion"
    return f"{engine.name} ({status})"
