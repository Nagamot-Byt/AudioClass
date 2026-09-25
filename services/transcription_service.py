"""services/transcription_service.py — Propiedad y ciclo de vida de los motores.

Extraido de la clase App (audioclass_v91.py). App ya no crea ni posee
LocalWhisperEngine / AudioPipeline / motor de adaptacion; los delega aqui.
Esto separa la orquestacion de motores de la interfaz y aisla el codigo que
antes provocaba bugs como el cierre de lambda (B023) por estar pegado a la UI.
"""

from audioclass_core import (
    AudioPipeline,
    GeminiAdaptationEngine,
    LocalWhisperEngine,
    OllamaAdaptationEngine,
    OpenAIAdaptationEngine,
    build_adaptation_engine,
)


class TranscriptionService:
    """Duenio de los motores de transcripcion/adaptacion y su ciclo de vida."""

    def __init__(self, config: dict | None = None, on_model_loaded=None):
        # Referencia al dict de config de App (no copia) para ver cambios en vivo.
        self.config = config if config is not None else {}
        self.on_model_loaded = on_model_loaded
        self.local_engine = None
        self.pipeline = None
        self.adapt_engine = None

    # ── Construccion ──────────────────────────────────────────────────────
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
        self.local_engine = LocalWhisperEngine(
            model_name=cfg.get("local_model", "base"),
            language=cfg.get("whisper_language", "auto"),
        )
        # La carga del modelo se dispara donde la hacia App originalmente
        # (self.local_engine.load(callback=...)), no aqui, para no cargarlo
        # en la construccion de la app.
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
        """Recrea el motor whisper local (cambio de modelo en caliente)."""
        if language is None:
            language = self.config.get("whisper_language", "auto")
        self.local_engine = LocalWhisperEngine(model_size, language)
        if self.on_model_loaded:
            self.local_engine.load(callback=self.on_model_loaded)
        self.config["local_model"] = model_size

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
        """Transcribe un audio con el motor local (delega en LocalWhisperEngine)."""
        return self.local_engine.transcribe(
            path,
            timestamps,
            cancel_event=cancel_event,
            progress_callback=progress_callback,
            partial_callback=partial_callback,
            check_silence=check_silence,
        )

    def adapt(self, text, template_name, progress_callback=None):
        """Adapta un texto con el motor de IA configurado (None si no hay key)."""
        if self.adapt_engine is None:
            return None
        return self.adapt_engine.adapt(text, template_name, progress_callback=progress_callback)
