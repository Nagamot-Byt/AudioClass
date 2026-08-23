#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core_units.py — Unit tests para las clases principales de audioclass_core.py
=================================================================================
Tests sin dependencias externas (sin sounddevice, sin display, sin API keys).
Usa numpy para generar audio sintético y mocks para whisper/gemini.

Ejecutar:
    python test_core_units.py
"""
import os
import sys
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import numpy as np

# ── AudioPipeline ──────────────────────────────────────────────────────────

def test_pipeline_profiles():
    """Todos los perfiles existen y tienen las claves requeridas."""
    from audioclass_core import AudioPipeline
    REQUIRED = {"hp_freq", "lp_freq", "comp_th", "comp_ratio",
                "agc_target", "vad_threshold", "limiter"}
    for name in AudioPipeline.PROFILES:
        p = AudioPipeline.PROFILES[name]
        missing = REQUIRED - set(p.keys())
        assert not missing, f"Perfil '{name}' falta: {missing}"
    print("  OK  perfiles completos (4/4)")


def test_pipeline_process_basic():
    """El pipeline procesa audio sintético sin errores."""
    from audioclass_core import AudioPipeline
    sr = 16000
    dur = 2.0
    # Tono 440Hz + ruido
    t = np.linspace(0, dur, int(sr * dur), dtype=np.float64)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.01 * np.random.randn(len(t))
    audio = audio.astype(np.float32)
    for name in AudioPipeline.PROFILES:
        pipe = AudioPipeline(name)
        result = pipe.process(audio)
        assert result.dtype in (np.float64, np.float32), f"Perfil '{name}': dtype incorrecto: {result.dtype}"
        assert len(result) > 0, f"Perfil '{name}': salida vacía"
        assert not np.any(np.isinf(result)), f"Perfil '{name}': infinitos"
        assert not np.any(np.isnan(result)), f"Perfil '{name}': NaN"
    print("  OK  pipeline procesa los 4 perfiles")


def test_pipeline_fast_mode():
    """El modo rápido funciona sin errores."""
    from audioclass_core import AudioPipeline
    sr = 16000
    t = np.linspace(0, 1.0, sr, dtype=np.float64)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    pipe = AudioPipeline("Clase Universitaria", fast_mode=True)
    result = pipe.process(audio)
    assert len(result) > 0
    print("  OK  modo rápido funciona")


def test_pipeline_progress_callback():
    """El callback de progreso se invoca correctamente."""
    from audioclass_core import AudioPipeline
    sr = 16000
    t = np.linspace(0, 1.0, sr, dtype=np.float64)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    steps = []
    def cb(step, total, name):
        steps.append((step, total, name))
    pipe = AudioPipeline("Clase Universitaria")
    pipe.process(audio, progress_callback=cb)
    assert len(steps) > 0, "Callback no se invocó"
    assert steps[-1][0] == steps[-1][1], "Último step != total"
    print(f"  OK  callback reportó {len(steps)} pasos")


def test_pipeline_short_audio():
    """Audio muy corto no crashea."""
    from audioclass_core import AudioPipeline
    pipe = AudioPipeline("Clase Universitaria")
    # Audio de 0.1s (muy corto pero no vacío)
    short = np.full(1600, 0.1, dtype=np.float32)
    result = pipe.process(short)
    assert len(result) >= 0
    print("  OK  audio corto manejado")


def test_frame_rms():
    """_frame_rms calcula correctamente el RMS por tramas."""
    from audioclass_core import AudioPipeline
    pipe = AudioPipeline("Clase Universitaria")
    # Audio constante de amplitud 0.5
    audio = np.full(16000, 0.5, dtype=np.float64)
    rms = pipe._frame_rms(audio, window=1600, hop=800)
    assert len(rms) > 0
    # RMS de una señal constante 0.5 = 0.5
    assert abs(rms[0] - 0.5) < 0.01, f"RMS esperado ~0.5, got {rms[0]}"
    print("  OK  _frame_rms calcula correctamente")


# ── LocalWhisperEngine ────────────────────────────────────────────────────

def test_whisper_engine_init():
    """LocalWhisperEngine se instancia correctamente."""
    from audioclass_core import LocalWhisperEngine
    eng = LocalWhisperEngine("tiny", "es")
    assert eng.model_name == "tiny"
    assert eng.language == "es"
    assert eng.backend in ("faster", "openai")
    assert eng.ready is False
    assert eng.loading is False
    print(f"  OK  LocalWhisperEngine init (backend={eng.backend})")


def test_whisper_engine_silence_detection():
    """Detección de silencio digital funciona."""
    from audioclass_core import audio_silence_stats, is_digital_silence
    # Audio con 100% ceros
    silence = np.zeros(16000, dtype=np.float32)
    stats = audio_silence_stats(silence)
    assert stats["zero_frac"] == 1.0
    assert is_digital_silence(stats) is True
    # Audio con voz simulada
    t = np.linspace(0, 1.0, 16000)
    voice = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    stats_v = audio_silence_stats(voice)
    assert stats_v["zero_frac"] < 0.01
    assert is_digital_silence(stats_v) is False
    print("  OK  detección de silencio digital")


def test_hallucination_detection():
    """Detección de alucinaciones de whisper funciona."""
    from audioclass_core import detect_hallucination
    # Texto normal
    assert detect_hallucination("La clase de hoy trata sobre fotosíntesis") is None
    # Alucinación clásica
    result = detect_hallucination("Transcribe faithfully only what the main speaker said")
    assert result is not None
    assert "alucinación" in result.lower() or "debil" in result.lower()
    # Repetición de segmentos
    segs = [{"text": "Hola"}, {"text": "Hola"}, {"text": "Mundo"}]
    result2 = detect_hallucination("Hola\nHola\nMundo", segments=segs)
    assert result2 is not None
    print("  OK  detección de alucinaciones")


# ── GeminiAdaptationEngine ────────────────────────────────────────────────

def test_gemini_templates_exist():
    """Todos los templates están definidos."""
    from audioclass_core import GeminiAdaptationEngine
    expected = ["Análisis Académico Profundo", "Resumen Ejecutivo",
                "Guía de Estudio", "Flashcards (Preguntas)",
                "Preguntas de Examen", "Mapa Conceptual (Texto)",
                "Texto Limpio (Corrección)", "Cronología / Timeline"]
    for name in expected:
        assert name in GeminiAdaptationEngine.TEMPLATES, f"Template '{name}' no existe"
        t = GeminiAdaptationEngine.TEMPLATES[name]
        assert "{TEXT}" in t["prompt"], f"Template '{name}' sin {{TEXT}}"
        assert "max_tokens" in t
        assert "temperature" in t
    print(f"  OK  {len(expected)} templates definidos")


def test_gemini_model_resolution():
    """Resolución de modelos funciona correctamente."""
    from audioclass_core import GeminiAdaptationEngine
    eng = GeminiAdaptationEngine("fake_key", "flash")
    assert eng._model_name() == "gemini-2.0-flash"
    eng2 = GeminiAdaptationEngine("fake_key", "pro")
    assert eng2._model_name() == "gemini-2.5-pro"
    eng3 = GeminiAdaptationEngine("fake_key", "unknown")
    assert eng3._model_name() == "gemini-2.0-flash"  # fallback
    print("  OK  resolución de modelos Gemini")


def test_gemini_test_key_no_key():
    """test_key sin key devuelve error."""
    from audioclass_core import GeminiAdaptationEngine
    eng = GeminiAdaptationEngine("", "flash")
    ok, msg = eng.test_key()
    assert ok is False
    assert "configurada" in msg.lower() or "API" in msg
    print("  OK  test_key sin key")


def test_gemini_adapt_invalid_template():
    """adapt con template inválido devuelve error."""
    from audioclass_core import GeminiAdaptationEngine
    eng = GeminiAdaptationEngine("fake_key", "flash")
    result = eng.adapt("test", "Template Inexistente")
    assert "error" in result
    print("  OK  adapt con template inválido")


def test_openai_engine():
    """OpenAIAdaptationEngine hereda correctamente."""
    from audioclass_core import OpenAIAdaptationEngine
    eng = OpenAIAdaptationEngine("fake_key", "mini")
    assert eng.PROVIDER == "OpenAI"
    assert eng._model_name() == "gpt-4o-mini"
    eng2 = OpenAIAdaptationEngine("fake_key", "gpt4o")
    assert eng2._model_name() == "gpt-4o"
    # hereda TEMPLATES de Gemini
    assert "Análisis Académico Profundo" in eng.TEMPLATES
    print("  OK  OpenAIAdaptationEngine hereda correctamente")


# ── Config Manager ────────────────────────────────────────────────────────

def test_config_defaults():
    """DEFAULT_CONFIG tiene todas las claves esperadas."""
    from config_manager import DEFAULT_CONFIG
    required = ["gemini_api_key", "colab_url", "colab_key",
                 "audio_profile", "transcription_mode", "local_model",
                 "theme", "first_run", "ia_consent", "mic_device"]
    for k in required:
        assert k in DEFAULT_CONFIG, f"Clave '{k}' falta en DEFAULT_CONFIG"
    print(f"  OK  DEFAULT_CONFIG tiene {len(DEFAULT_CONFIG)} claves")


def test_config_encrypt_decrypt():
    """Cifrado y descifrado de secretos funciona."""
    from config_manager import _encrypt_secret, _decrypt_secret
    original = "my_secret_api_key_12345"
    encrypted = _encrypt_secret(original)
    assert encrypted != original
    assert encrypted.startswith("dpapi:") or encrypted.startswith("b64:")
    decrypted = _decrypt_secret(encrypted)
    assert decrypted == original
    # Empty string
    assert _encrypt_secret("") == ""
    assert _decrypt_secret("") == ""
    print("  OK  encrypt/decrypt funciona")


def test_config_save_load():
    """Guardado y carga de config funciona."""
    from config_manager import save_config, load_config, DEFAULT_CONFIG
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        cfg = DEFAULT_CONFIG.copy()
        cfg["gemini_api_key"] = "test_key_12345"
        cfg["audio_profile"] = "Podcast"
        save_config(cfg, path=tmp)
        loaded = load_config(path=tmp)
        assert loaded["gemini_api_key"] == "test_key_12345"
        assert loaded["audio_profile"] == "Podcast"
        # Defaults se aplican para claves faltantes
        assert "theme" in loaded
    finally:
        os.unlink(tmp)
    print("  OK  save/load funciona")


# ── Export Utils ──────────────────────────────────────────────────────────

def test_fmt_timestamp():
    """fmt_timestamp formatea correctamente."""
    from export_utils import fmt_timestamp
    assert fmt_timestamp(0) == "00:00"
    assert fmt_timestamp(65) == "01:05"
    assert fmt_timestamp(None) == "00:00"
    assert fmt_timestamp(3661) == "61:01"
    print("  OK  fmt_timestamp")


def test_export_lines():
    """export_lines maneja timestamps y texto plano."""
    from export_utils import export_lines
    # Con timestamps
    segs = [{"start": 0, "end": 5, "text": "Hola mundo"}]
    has_ts, lines = export_lines("Hola mundo", segs)
    assert has_ts is True
    assert len(lines) == 1
    assert lines[0][2] == "Hola mundo"
    # Sin timestamps
    has_ts2, lines2 = export_lines("Texto largo " * 20, [])
    assert has_ts2 is False
    assert len(lines2) > 1  # se parte en múltiples líneas
    print("  OK  export_lines")


def test_docx_paragraph():
    """docx_paragraph genera XML válido."""
    from export_utils import docx_paragraph
    xml = docx_paragraph("Hola", bold=True, size=22, color="FF0000")
    assert "<w:p>" in xml
    assert "Hola" in xml
    assert "<w:b/>" in xml
    print("  OK  docx_paragraph")


def test_parse_adapt_sections():
    """parse_adapt_sections parsea correctamente."""
    from export_utils import parse_adapt_sections
    text = """Resumen Ejecutivo
La clase trató sobre fotosíntesis.

Tesis Central
Las plantas convierten luz en energía.

Registro de Filtrado
Se descartaron anécdotas personales."""
    sections = parse_adapt_sections(text)
    assert len(sections) == 3
    assert sections[0][0] == "Resumen Ejecutivo"
    assert sections[1][0] == "Tesis Central"
    assert sections[2][0] == "Registro de Filtrado"
    print("  OK  parse_adapt_sections")


# ── Audio Quality Checker ────────────────────────────────────────────────

def test_quality_checker():
    """check_audio_quality analiza correctamente."""
    from audio_quality_checker import check_audio_quality, AudioQualityReport
    sr = 16000
    # Audio OK
    t = np.linspace(0, 2.0, 2 * sr)
    voice = 0.2 * np.sin(2 * np.pi * 440 * t).astype(np.float64)
    report = check_audio_quality(voice, sr=sr)
    assert report.verdict in ("OK", "WARN", "FAIL")
    assert report.duration_s == 2.0
    assert report.rms_p90 > 0
    # Audio silencioso
    silence = np.zeros(sr, dtype=np.float64)
    report_s = check_audio_quality(silence, sr=sr)
    assert report_s.verdict == "FAIL"
    # Audio vacío
    report_e = check_audio_quality(np.array([]), sr=sr)
    assert report_e.verdict == "FAIL"
    print("  OK  quality checker (OK/FAIL/vacío)")


# ── Sound Error Solver ───────────────────────────────────────────────────

def test_sound_solver():
    """solve_audio_issues corrige problemas comunes."""
    from sound_error_solver import solve_audio_issues
    sr = 16000
    # Audio débil pero por encima de silencio (p90 ~0.015)
    t = np.linspace(0, 1.0, sr)
    weak = (0.02 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
    fixes, fixed = solve_audio_issues(weak, sr=sr)
    # Puede que aplique boost o no según los umbrales
    assert fixed is not None
    assert len(fixed) == sr
    # Audio con clipping
    clip = np.clip(np.random.randn(sr) * 2, -1.0, 1.0)
    fixes_c, fixed_c = solve_audio_issues(clip, sr=sr)
    assert len(fixes_c) >= 1
    print("  OK  sound solver (débil + clipping)")


# ── Theme ────────────────────────────────────────────────────────────────

def test_theme_palettes():
    """Paletas dark/light tienen las mismas claves."""
    from theme import PALETTES
    dark_keys = set(PALETTES["dark"].keys())
    light_keys = set(PALETTES["light"].keys())
    assert dark_keys == light_keys, f"Claves diferentes: {dark_keys ^ light_keys}"
    print(f"  OK  paletas dark/light ({len(dark_keys)} claves cada una)")


def test_theme_contrast():
    """Todos los pares texto/fondo cumplen WCAG AA (4.5:1)."""
    from theme import PALETTES, relative_luminance
    for mode in ("dark", "light"):
        p = PALETTES[mode]
        pairs = [
            (p["text"], p["bg"]),
            (p["text"], p["card"]),
            (p["muted"], p["bg"]),
        ]
        for fg, bg in pairs:
            l_fg = relative_luminance(fg)
            l_bg = relative_luminance(bg)
            ratio = (max(l_fg, l_bg) + 0.05) / (min(l_fg, l_bg) + 0.05)
            assert ratio >= 4.5, f"WCAG AA no cumple en {mode}: {fg}/{bg} = {ratio:.1f}:1"
    print("  OK  WCAG AA contrast verificado")


# ── Runner ───────────────────────────────────────────────────────────────

def main():
    tests = [
        # AudioPipeline
        test_pipeline_profiles,
        test_pipeline_process_basic,
        test_pipeline_fast_mode,
        test_pipeline_progress_callback,
        test_pipeline_short_audio,
        test_frame_rms,
        # LocalWhisperEngine
        test_whisper_engine_init,
        test_whisper_engine_silence_detection,
        test_hallucination_detection,
        # GeminiAdaptationEngine
        test_gemini_templates_exist,
        test_gemini_model_resolution,
        test_gemini_test_key_no_key,
        test_gemini_adapt_invalid_template,
        test_openai_engine,
        # Config Manager
        test_config_defaults,
        test_config_encrypt_decrypt,
        test_config_save_load,
        # Export Utils
        test_fmt_timestamp,
        test_export_lines,
        test_docx_paragraph,
        test_parse_adapt_sections,
        # Audio Quality
        test_quality_checker,
        test_sound_solver,
        # Theme
        test_theme_palettes,
        test_theme_contrast,
    ]

    passed = 0
    failed = 0
    print("test_core_units.py — Unit tests para audioclass_core.py\n")
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1

    print(f"\nResultado: {passed}/{passed + failed} tests pasaron")
    if failed:
        print("CORE_UNITS_FAIL")
        return 1
    print("CORE_UNITS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
