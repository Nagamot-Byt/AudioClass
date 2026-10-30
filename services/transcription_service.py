"""services/transcription_service.py — Propiedad y ciclo de vida de los motores.

Extraido de la clase App (audioclass_v91.py). App ya no crea ni posee
LocalWhisperEngine / AudioPipeline / motor de adaptacion; los delega aqui.
Gestiona el ciclo de vida de memoria (descarga por inactividad VRAM/RAM) y
la coordinacion con ModelManager.
"""

from __future__ import annotations

import time
from typing import Any

from audioclass_core import (
    AudioPipeline,
    GeminiAdaptationEngine,
    LocalWhisperEngine,
    OllamaAdaptationEngine,
    OpenAIAdaptationEngine,
    build_adaptation_engine,
)
from services.model_manager import ModelManager, get_default_model_manager


class TranscriptionService:
    """Dueño de los motores de transcripción/adaptación y su ciclo de vida."""

    def __init__(self, config: dict | None = None, on_model_loaded=None):
        # Referencia al dict de config de App (no copia) para ver cambios en vivo.
        self.config = config if config is not None else {}
        self.on_model_loaded = on_model_loaded
        self.local_engine: Any = None
        self.pipeline: Any = None
        self.adapt_engine: Any = None
        self.model_manager: ModelManager = get_default_model_manager()
        self.last_activity: float = time.time()
        self.idle_timeout: float = float(self.config.get("idle_unload_timeout", 300.0))
        self._is_transcribing: bool = False

    # ── Construcción ──────────────────────────────────────────────────────
    def build(self, config: dict | None = None):
        """Crea pipeline, motor whisper local y motor de adaptacion desde config."""
        if config is not None:
            self.config = config
        cfg = self.config
        self.pipeline = AudioPipeline(
            profile_name=cfg.get("audio_profile", "Clase Universitaria"),
            fast_mode=cfg.get("fast_mode", False),
            use_vad=cfg.get("use_vad", True),
        )
        mode = cfg.get("transcription_mode") or cfg.get("mode", "local")
        if mode == "parakeet":
            from audioclass_core import SherpaParakeetEngine

            self.local_engine = SherpaParakeetEngine()
        else:
            self.local_engine = LocalWhisperEngine(
                model_name=cfg.get("local_model", "base"),
                language=cfg.get("whisper_language", "auto"),
            )
        self.adapt_engine = self._build_adapt_engine()
        return self

    def _build_adapt_engine(self):
        """Construye el motor de adaptacion segun adapt_provider y la API key.

        Devuelve SIEMPRE una instancia del motor (aun con clave vacia), igual
        que la implementacion original en App: el motor valida la clave al usarla.
        """
        cfg = self.config
        return build_adaptation_engine(
            provider=cfg.get("adapt_provider", "gemini"),
            gemini_api_key=cfg.get("gemini_api_key", ""),
            gemini_model=cfg.get("gemini_model", "flash"),
            openai_api_key=cfg.get("openai_api_key", ""),
            openai_model=cfg.get("openai_model", "mini"),
            ollama_url=cfg.get("ollama_url", "http://localhost:11434"),
            ollama_model=cfg.get("ollama_model", "qwen2.5"),
        )

    def set_local_model(self, model_size: str, language: str | None = None):
        """Recrea el motor whisper local (cambio de modelo en caliente), liberando memoria previa."""
        self.unload_engines()
        if language is None:
            language = self.config.get("whisper_language", "auto")
        self.local_engine = LocalWhisperEngine(model_size, language)
        if self.on_model_loaded:
            self.local_engine.load(callback=self.on_model_loaded)
        self.config["local_model"] = model_size
        self.last_activity = time.time()

    # ── Gestión de Ciclo de Vida y Memoria (VRAM/RAM) ─────────────────────
    def unload_engines(self, force: bool = False) -> bool:
        """Descarga el motor de IA activo de la memoria RAM/VRAM para liberar recursos."""
        if not force and self._is_transcribing:
            return False
        if self.local_engine is not None and hasattr(self.local_engine, "unload"):
            try:
                self.local_engine.unload()
                return True
            except Exception:
                pass
        return False

    def check_idle_unload(self, timeout: float | None = None) -> bool:
        """Comprueba si el motor ha estado inactivo más tiempo del umbral y lo descarga."""
        if self._is_transcribing:
            return False
        limit = timeout if timeout is not None else self.idle_timeout
        if limit <= 0:
            return False  # Inactividad deshabilitada
        if time.time() - self.last_activity >= limit:
            if self.local_engine is not None and getattr(self.local_engine, "ready", False):
                return self.unload_engines()
        return False

    # ── Operaciones ───────────────────────────────────────────────────────
    def transcribe(
        self,
        path,
        timestamps: bool = True,
        cancel_event=None,
        progress_callback=None,
        partial_callback=None,
        check_silence: bool = True,
    ) -> dict:
        """Transcribe un audio con el motor local asegurando actualización de actividad."""
        self.last_activity = time.time()
        self._is_transcribing = True
        try:
            return self.local_engine.transcribe(
                path,
                timestamps,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                partial_callback=partial_callback,
                check_silence=check_silence,
            )
        finally:
            self._is_transcribing = False
            self.last_activity = time.time()

    def adapt(self, text, template_name, progress_callback=None):
        """Adapta un texto con el motor de IA configurado (None si no hay key)."""
        if self.adapt_engine is None:
            return None
        return self.adapt_engine.adapt(text, template_name, progress_callback=progress_callback)
