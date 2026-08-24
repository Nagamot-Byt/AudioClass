"""app_metrics.py — Metricas de uso para monitoreo y analisis.

Registra eventos de transcription, export, y uso de features.
Expone metricas en formato Prometheus-compatible (/metrics endpoint)
y genera reportes internos para el dashboard de administracion.

Uso:
    from app_metrics import record_transcription, record_export, get_summary

    record_transcription(duration=10.0, model="tiny", provider="local")
    summary = get_summary()
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from typing import Any

# Archivo de persistencia
_METRICS_DIR = os.path.join(os.path.expanduser("~"), ".audioclass")
_METRICS_FILE = os.path.join(_METRICS_DIR, "metrics.json")

# Cache en memoria
_lock = threading.Lock()
_counters = defaultdict(int)
_timers = defaultdict(list)
_start_time = time.time()


def _ensure_dir():
    """Asegura que el directorio de metricas exista."""
    os.makedirs(_METRICS_DIR, exist_ok=True)


def _load():
    """Carga metricas desde disco."""
    global _counters, _timers
    try:
        if os.path.exists(_METRICS_FILE):
            with open(_METRICS_FILE) as f:
                data = json.load(f)
            _counters = defaultdict(int, data.get("counters", {}))
            _timers = defaultdict(list, data.get("timers", {}))
    except Exception:
        pass


def _save():
    """Guarda metricas a disco."""
    try:
        _ensure_dir()
        # Limitar timers a los ultimos 1000 por key
        trimmed = {k: v[-1000:] for k, v in _timers.items()}
        with open(_METRICS_FILE, "w") as f:
            json.dump({"counters": dict(_counters), "timers": trimmed}, f)
    except Exception:
        pass


def _increment(key, count=1):
    """Incrementa un contador."""
    with _lock:
        _counters[key] += count
        _save()


def _record_timer(key, value):
    """Registra un valor de tiempo."""
    with _lock:
        _timers[key].append(value)
        _save()


def record_transcription(duration: float, model: str = "unknown", provider: str = "local") -> None:
    """Registra un evento de transcripcion.

    Args:
        duration: Duracion en segundos del audio transcrito.
        model: Nombre del modelo usado (tiny, base, small, etc).
        provider: Proveedor (local, gemini, openai, colab).
    """
    _increment("transcriptions")
    _increment(f"transcriptions.model.{model}")
    _increment(f"transcriptions.provider.{provider}")
    _record_timer("transcription_duration", duration)
    _record_timer(f"transcription_duration.{model}", duration)
    _increment("audio_seconds", int(duration))


def record_export(format: str = "pdf") -> None:
    """Registra un evento de exportacion.

    Args:
        format: Formato de exportacion (pdf, docx, google_docs, txt).
    """
    _increment("exports")
    _increment(f"exports.format.{format}")


def record_feature(feature: str) -> None:
    """Registra el uso de una feature.

    Args:
        feature: Nombre de la feature (e.g., 'adaptation', 'waveform', 'plugin').
    """
    _increment(f"feature.{feature}")


def record_error(error_type: str) -> None:
    """Registra un error.

    Args:
        error_type: Tipo de error (e.g., 'api_timeout', 'mic_error', 'export_fail').
    """
    _increment("errors")
    _increment(f"error.{error_type}")


def record_session() -> None:
    """Registra el inicio de una sesion."""
    _increment("sessions")


def get_summary() -> dict[str, Any]:
    """Devuelve un resumen de todas las metricas.

    Returns:
        dict con contadores y timers.
    """
    with _lock:
        avg_duration = 0.0
        durations = _timers.get("transcription_duration", [])
        if durations:
            avg_duration = sum(durations) / len(durations)

        return {
            "transcriptions": _counters.get("transcriptions", 0),
            "exports": _counters.get("exports", 0),
            "sessions": _counters.get("sessions", 0),
            "errors": _counters.get("errors", 0),
            "audio_seconds_total": _counters.get("audio_seconds", 0),
            "avg_transcription_duration": round(avg_duration, 2),
            "uptime_seconds": round(time.time() - _start_time, 1),
            "models_used": {k.split(".")[-1]: v for k, v in _counters.items() if k.startswith("transcriptions.model.")},
            "providers_used": {
                k.split(".")[-1]: v for k, v in _counters.items() if k.startswith("transcriptions.provider.")
            },
            "exports_by_format": {k.split(".")[-1]: v for k, v in _counters.items() if k.startswith("exports.format.")},
        }


def to_prometheus_text() -> str:
    """Expone metricas en formato Prometheus text exposition.

    Returns:
        str con formato Prometheus (multiline).
    """
    lines = []
    s = get_summary()

    lines.append("# HELP audioclass_transcriptions_total Total transcriptions performed")
    lines.append("# TYPE audioclass_transcriptions_total counter")
    lines.append(f"audioclass_transcriptions_total {s['transcriptions']}")

    lines.append("# HELP audioclass_exports_total Total exports performed")
    lines.append("# TYPE audioclass_exports_total counter")
    lines.append(f"audioclass_exports_total {s['exports']}")

    lines.append("# HELP audioclass_sessions_total Total sessions")
    lines.append("# TYPE audioclass_sessions_total counter")
    lines.append(f"audioclass_sessions_total {s['sessions']}")

    lines.append("# HELP audioclass_errors_total Total errors")
    lines.append("# TYPE audioclass_errors_total counter")
    lines.append(f"audioclass_errors_total {s['errors']}")

    lines.append("# HELP audioclass_audio_seconds_total Total audio seconds processed")
    lines.append("# TYPE audioclass_audio_seconds_total counter")
    lines.append(f"audioclass_audio_seconds_total {s['audio_seconds_total']}")

    lines.append("# HELP audioclass_transcription_duration_avg Average transcription duration")
    lines.append("# TYPE audioclass_transcription_duration_avg gauge")
    lines.append(f"audioclass_transcription_duration_avg {s['avg_transcription_duration']}")

    lines.append("# HELP audioclass_uptime_seconds Process uptime")
    lines.append("# TYPE audioclass_uptime_seconds gauge")
    lines.append(f"audioclass_uptime_seconds {s['uptime_seconds']}")

    for model, count in s.get("models_used", {}).items():
        lines.append(f'audioclass_transcriptions_by_model{{model="{model}"}} {count}')

    for provider, count in s.get("providers_used", {}).items():
        lines.append(f'audioclass_transcriptions_by_provider{{provider="{provider}"}} {count}')

    return "\n".join(lines) + "\n"


# Load on import
_load()
