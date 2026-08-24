#!/usr/bin/env python3
"""
ai_providers.py — Sistema de plugins para proveedores de IA
============================================================
Registry extensible para motores de transcripción y adaptación.
Permite agregar nuevos proveedores sin modificar el código existente.

Uso:
    from ai_providers import ProviderRegistry

    # Registrar un proveedor nuevo
    registry = ProviderRegistry()
    registry.register_transcription("mi_motor", MiMotorTranscripcion)

    # Listar motores disponibles
    engines = registry.get_available_transcription_engines(config)
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranscriptionProvider:
    """Define un proveedor de transcripción disponible."""

    name: str
    key: str
    requires_key: bool = False
    requires_url: bool = False
    description: str = ""
    config_key_api: str = ""  # Clave en config para la API key
    config_key_model: str = ""  # Clave en config para el modelo
    config_key_url: str = ""  # Clave en config para la URL


@dataclass
class AdaptationProvider:
    """Define un proveedor de adaptación (análisis con IA) disponible."""

    name: str
    key: str
    requires_key: bool = True
    description: str = ""
    config_key_api: str = ""
    config_key_model: str = ""
    models: dict[str, str] = field(default_factory=dict)  # alias -> model_id
    engine_class: Any | None = None  # Clase del motor (lazy import)


class ProviderRegistry:
    """Registry extensible de proveedores de IA.

    Permite registrar nuevos motores de transcripción y adaptación
    sin modificar el código existente. La UI puede consultarlo
    para poblar selectores/dropdowns.

    Ejemplo:
        registry = ProviderRegistry()
        registry.register_adaptation("anthropic", AdaptationProvider(
            name="Anthropic (Claude)",
            key="anthropic",
            config_key_api="anthropic_api_key",
            models={"claude-sonnet": "claude-sonnet-4-20250514"},
        ))
    """

    def __init__(self):
        self._transcription: dict[str, TranscriptionProvider] = {}
        self._adaptation: dict[str, AdaptationProvider] = {}

    # ── Transcripción ──────────────────────────────────────────────────────

    def register_transcription(self, key: str, provider: TranscriptionProvider) -> None:
        """Registra un proveedor de transcripción."""
        self._transcription[key] = provider

    def get_transcription(self, key: str) -> TranscriptionProvider | None:
        """Obtiene un proveedor de transcripción por clave."""
        return self._transcription.get(key)

    def get_all_transcription(self) -> dict[str, TranscriptionProvider]:
        """Devuelve todos los proveedores de transcripción registrados."""
        return dict(self._transcription)

    def get_available_transcription_engines(self, config: dict) -> list[tuple[str, TranscriptionProvider, bool]]:
        """Devuelve la lista de motores de transcripción con su disponibilidad.

        Returns:
            Lista de (key, provider, available) donde available indica
            si el motor puede usarse (tiene API key si la necesita).
        """
        result = []
        for key, provider in self._transcription.items():
            available = True
            if provider.requires_key and provider.config_key_api:
                available = bool(config.get(provider.config_key_api))
            if provider.requires_url and provider.config_key_url:
                available = bool(config.get(provider.config_key_url))
            result.append((key, provider, available))
        return result

    def select_transcription_engine(self, config: dict) -> tuple[str | None, TranscriptionProvider | None]:
        """Selecciona el motor de transcripción según la configuración."""
        mode = config.get("transcription_mode", "local")

        # Buscar por clave directa
        if mode in self._transcription:
            provider = self._transcription[mode]
            if provider.requires_key and provider.config_key_api:
                if not config.get(provider.config_key_api):
                    return None, None
            if provider.requires_url and provider.config_key_url:
                if not config.get(provider.config_key_url):
                    return None, None
            return mode, provider

        # Mapeo de modos legacy
        legacy_map = {
            "cloud": "colab",
            "local_whisper": "local_whisper",
        }
        mapped = legacy_map.get(mode, mode)
        if mapped in self._transcription:
            return mapped, self._transcription[mapped]

        # Fallback: local
        if "local" in self._transcription:
            return "local", self._transcription["local"]

        return None, None

    # ── Adaptación ─────────────────────────────────────────────────────────

    def register_adaptation(self, key: str, provider: AdaptationProvider) -> None:
        """Registra un proveedor de adaptación (análisis con IA)."""
        self._adaptation[key] = provider

    def get_adaptation(self, key: str) -> AdaptationProvider | None:
        """Obtiene un proveedor de adaptación por clave."""
        return self._adaptation.get(key)

    def get_all_adaptation(self) -> dict[str, AdaptationProvider]:
        """Devuelve todos los proveedores de adaptación registrados."""
        return dict(self._adaptation)

    def get_available_adaptation_engines(self, config: dict) -> list[tuple[str, AdaptationProvider, bool]]:
        """Devuelve la lista de motores de adaptación con su disponibilidad."""
        result = []
        for key, provider in self._adaptation.items():
            available = True
            if provider.requires_key and provider.config_key_api:
                available = bool(config.get(provider.config_key_api))
            result.append((key, provider, available))
        return result

    def build_adaptation_engine(self, provider_key: str, config: dict):
        """Construye una instancia del motor de adaptación.

        Args:
            provider_key: Clave del proveedor (ej: 'gemini', 'openai').
            config: Dict de configuración con las API keys.

        Returns:
            Instancia del motor de adaptación o None si no se puede construir.
        """
        provider = self._adaptation.get(provider_key)
        if provider is None:
            return None

        if provider.requires_key and provider.config_key_api:
            api_key = config.get(provider.config_key_api, "")
            if not api_key:
                return None
        else:
            api_key = ""

        model = config.get(provider.config_key_model, "") if provider.config_key_model else ""

        if provider.engine_class is None:
            return None

        return provider.engine_class(api_key=api_key, model=model)


# ── Registry por defecto ──────────────────────────────────────────────────


def create_default_registry() -> ProviderRegistry:
    """Crea el registry con los proveedores incorporados de AudioClass."""
    registry = ProviderRegistry()

    # ── Transcripción ──────────────────────────────────────────────────────
    registry.register_transcription(
        "local",
        TranscriptionProvider(
            name="Local (faster-whisper)",
            key="local",
            requires_key=False,
            description="Transcripcion offline con modelos Tiny/Base/Small. Sin internet.",
        ),
    )
    registry.register_transcription(
        "local_whisper",
        TranscriptionProvider(
            name="Local (openai-whisper)",
            key="local_whisper",
            requires_key=False,
            description="Transcripcion offline con openai-whisper. Mas lento que faster-whisper.",
        ),
    )
    registry.register_transcription(
        "gemini",
        TranscriptionProvider(
            name="Gemini (Google AI)",
            key="gemini",
            requires_key=True,
            description="Transcripcion remota via Google Gemini. Rapido y preciso.",
            config_key_api="gemini_api_key",
        ),
    )
    registry.register_transcription(
        "openai",
        TranscriptionProvider(
            name="OpenAI (GPT)",
            key="openai",
            requires_key=True,
            description="Transcripcion remota via OpenAI API. Alta calidad.",
            config_key_api="openai_api_key",
        ),
    )
    registry.register_transcription(
        "colab",
        TranscriptionProvider(
            name="Colab (GPU remota)",
            key="colab",
            requires_key=False,
            requires_url=True,
            description="Transcripcion via Google Colab con GPU. Requiere URL del servidor.",
            config_key_url="colab_url",
        ),
    )

    # ── Adaptación (análisis con IA) ───────────────────────────────────────
    # Lazy import para no cargar los motores al importar el módulo
    def _lazy_gemini(**kwargs):
        from audioclass_core import GeminiAdaptationEngine

        return GeminiAdaptationEngine(**kwargs)

    def _lazy_openai(**kwargs):
        from audioclass_core import OpenAIAdaptationEngine

        return OpenAIAdaptationEngine(**kwargs)

    registry.register_adaptation(
        "gemini",
        AdaptationProvider(
            name="Gemini (Google AI)",
            key="gemini",
            requires_key=True,
            description="Analisis con Gemini. Gratis en aistudio.google.com/app/apikey",
            config_key_api="gemini_api_key",
            config_key_model="gemini_model",
            models={"flash": "gemini-2.0-flash", "pro": "gemini-2.5-pro"},
            engine_class=_lazy_gemini,
        ),
    )
    registry.register_adaptation(
        "openai",
        AdaptationProvider(
            name="OpenAI (GPT)",
            key="openai",
            requires_key=True,
            description="Analisis con GPT. Gratis con plan inicial en platform.openai.com",
            config_key_api="openai_api_key",
            config_key_model="openai_model",
            models={"mini": "gpt-4o-mini", "gpt4o": "gpt-4o"},
            engine_class=_lazy_openai,
        ),
    )

    return registry


# Singleton global (lazy)
_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    """Obtiene el registry global (se crea en la primera llamada)."""
    global _registry
    if _registry is None:
        _registry = create_default_registry()
    return _registry
