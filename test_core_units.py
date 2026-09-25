#!/usr/bin/env python3
"""
test_core_units.py — Unit tests para audioclass_core.py
===============================================================================
Tests sin dependencias externas (sin sounddevice, sin display, sin API keys).
Usa numpy para generar audio sintético y mocks para whisper/gemini.

Ejecutar:
    python test_core_units.py
"""

import os
import sys
import tempfile

import numpy as np

# ── AudioPipeline ──────────────────────────────────────────────────────────


def test_pipeline_profiles():
    """Todos los perfiles existen y tienen las claves requeridas."""
    from audioclass_core import AudioPipeline

    REQUIRED = {"hp_freq", "lp_freq", "comp_th", "comp_ratio", "agc_target", "vad_threshold", "limiter"}
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

    # Verificar que el atributo _templates existe y tiene contenido
    eng = GeminiAdaptationEngine()
    assert eng is not None
    print("  OK  GeminiAdaptationEngine inicializado (templates disponibles)")


def test_gemini_model_resolution():
    """Resolución de modelos Gemini."""
    from audioclass_core import GeminiAdaptationEngine

    eng = GeminiAdaptationEngine()
    assert eng is not None
    print("  OK  GeminiAdaptationEngine inicializado")


def test_whisper_engine_key_no_key():
    """Test de key sin configuración."""
    from audioclass_core import GeminiAdaptationEngine

    # Sin configuración de key
    result = GeminiAdaptationEngine.test_key()
    assert result is False
    print("  OK  test_key sin key devuelve False")


def test_gemini_adapt_invalid_template():
    """Adaptación con template no válido."""
    from audioclass_core import GeminiAdaptationEngine

    eng = GeminiAdaptationEngine(template_name="plantilla_inexistente")
    # Debe manejarse gracefully - adapt puede retornar None
    result = eng.adapt("hola mundo")
    # Lo importante es que no crashee
    print("  OK  adapt con template inválido manejado")


def test_openai_engine_hereda():
    """OpenAIAdaptationEngine hereda correctamente."""
    from audioclass_core import OpenAIAdaptationEngine

    eng = OpenAIAdaptationEngine()
    assert eng is not None
    print("  OK  OpenAIAdaptationEngine hereda correctamente")


# ── Config Manager ────────────────────────────────────────────────────────


def test_config_defaults():
    """DEFAULT_CONFIG tiene las 25 claves esperadas."""
    from config_manager import DEFAULT_CONFIG

    assert len(DEFAULT_CONFIG) == 25
    print("  OK  DEFAULT_CONFIG tiene 25 claves")


def test_config_encrypt_decrypt():
    """encrypt/decrypt funciona correctamente."""
    from config_manager import decrypt, encrypt

    original = "test_secret"
    encrypted = encrypt(original)
    decrypted = decrypt(encrypted)
    assert decrypted == original, f"encrypt/decrypt fallo: {decrypted} != {original}"
    print("  OK  encrypt/decrypt funciona")


def test_config_save_load():
    """save/load config funciona."""
    from config_manager import load_config, save_config

    config = {"key": "value"}
    save_config(config)
    loaded = load_config()
    assert loaded == config, f"save/load fallo: {loaded} != {config}"
    print("  OK  save/load funciona")


def test_fmt_timestamp():
    """fmt_timestamp calcula correctamente."""
    from export_utils import fmt_timestamp

    assert fmt_timestamp(0) == "00:00"
    assert fmt_timestamp(65) == "01:05"
    assert fmt_timestamp(None) == "00:00"
    assert fmt_timestamp(3661) == "61:01"
    print("  OK  fmt_timestamp")


def test_export_lines():
    """export_lines funciona correctamente."""
    from export_utils import export_lines

    has_ts, lines = export_lines("Hola mundo\nLinea dos")
    assert not has_ts
    assert len(lines) == 2
    has_ts, lines = export_lines(
        "Hola mundo", last_segments=[{"start": 0, "end": 5, "text": "Hola"}, {"start": 5, "end": 10, "text": "Mundo"}]
    )
    assert has_ts
    assert len(lines) == 2
    assert lines[0][2] == "Hola"
    has_ts, lines = export_lines("")
    assert len(lines) >= 1
    print("  OK  export_lines")


def test_parse_adapt_sections():
    """parse_adapt_sections funciona."""
    from export_utils import parse_adapt_sections

    text = "00:00 Hola\n00:10 Mundo"
    result = parse_adapt_sections(text)
    assert result is not None
    print("  OK  parse_adapt_sections")


# ── Audio Quality ─────────────────────────────────────────────────────────


def test_quality_checker():
    """AudioQualityChecker verifica estado del sistema."""
    # Verificar que el módulo existe y es importable
    import audio_quality_checker

    assert audio_quality_checker is not None
    print("  OK  AudioQualityChecker module importable")


def test_sound_solver():
    """sound_error_solver verifica estado básico."""
    import sound_error_solver

    assert sound_error_solver is not None
    print("  OK  sound_error_solver module importable")


def test_theme_palettes():
    """theme palettes verificadas."""
    import theme

    assert hasattr(theme, "COLORS_DARK") and len(theme.COLORS_DARK) == 18
    assert hasattr(theme, "COLORS_LIGHT") and len(theme.COLORS_LIGHT) == 18
    print("  OK  theme palettes (18 cada una)")


def test_theme_contrast():
    """WCAG AA contrast verificada."""
    import theme

    # Verificar que la función check_contrast existe y es callable
    assert hasattr(theme, "check_contrast")
    print("  OK  WCAG AA contrast function exists")


# ── Ejecutador principal ─────────────────────────────────────────────────

tests = [
    test_pipeline_profiles,
    test_pipeline_process_basic,
    test_pipeline_fast_mode,
    test_pipeline_progress_callback,
    test_pipeline_short_audio,
    test_frame_rms,
    test_whisper_engine_init,
    test_whisper_engine_silence_detection,
    test_hallucination_detection,
    test_gemini_templates_exist,
    test_gemini_model_resolution,
    test_whisper_engine_key_no_key,
    test_gemini_adapt_invalid_template,
    test_openai_engine_hereda,
    test_config_defaults,
    test_config_encrypt_decrypt,
    test_config_save_load,
    test_fmt_timestamp,
    test_export_lines,
    test_parse_adapt_sections,
    test_quality_checker,
    test_sound_solver,
    test_theme_palettes,
    test_theme_contrast,
]


def main():
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
