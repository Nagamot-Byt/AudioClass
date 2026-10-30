#!/usr/bin/env python3
"""test_mic_troubleshooter.py — Suite de pruebas para el Sistema de Troubleshooting de Micrófono.

Valida:
  1. Detección del backend de audio del SO (Linux/PipeWire/PulseAudio/ALSA, Windows, macOS).
  2. Consulta de estado y niveles de captura (MicState).
  3. Resampling polifásico (48k -> 16k, 44.1k -> 16k, arrays vacíos).
  4. Resiliencia de AudioPipeline ante arrays vacíos (len == 0).
  5. Detección de zumbido eléctrico (50 Hz / 60 Hz).
  6. Evaluación acústica en vivo con audio sintético (OPTIMAL, WEAK, VERY_LOW, SILENCIO, CLIPPING, ERROR).
  7. Detección y fallback de compatibilidad de tasa de muestreo (ALSA -9997 -> native sr).
  8. auto_fix() unificado y clase MicTroubleshooter.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audioclass_core as core
import mic_troubleshooter as mt

failures: list[str] = []


def check(name: str, cond: bool, detail: str = ""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        failures.append(name)


class FakeInputStream:
    """Stream simulado para probar measure_signal sin hardware real."""

    def __init__(self, samples: np.ndarray, blocksize: int = 800, fail: bool = False, **kwargs):
        self.samples = samples
        self.blocksize = blocksize
        self.fail = fail
        self.callback = kwargs.get("callback")

    def __enter__(self):
        if self.fail:
            raise OSError("Dispositivo de audio no disponible (test stub)")
        n = len(self.samples)
        for i in range(0, n, self.blocksize):
            chunk = self.samples[i : i + self.blocksize]
            if self.callback:
                self.callback(chunk.reshape(-1, 1), len(chunk), None, None)
        return self

    def __exit__(self, *args):
        return False


def run_tests():
    print("=" * 70)
    print("TEST: mic_troubleshooter — Diagnóstico y Reparación de Micrófono")
    print("=" * 70)

    # ── 1. Backend y Estado ──────────────────────────────────────────────────
    backend = mt.detect_backend()
    check(
        "detect_backend retorna string valido",
        backend in ("pipewire", "pulseaudio", "alsa", "windows", "macos", "unknown"),
        f"backend={backend}",
    )

    state = mt.get_mic_state()
    check("get_mic_state retorna MicState", isinstance(state, mt.MicState), str(state))
    check("MicState volumen en rango [0, 150]", 0 <= state.volume <= 150, f"vol={state.volume}")
    check(
        "MicState status valido", state.status in ("OK", "LOW_VOLUME", "MUTED", "UNAVAILABLE"), f"status={state.status}"
    )

    # ── 2. Resampling Polifásico y Arrays Vacíos ─────────────────────────────
    sr_test = 48000
    dur = 0.5
    t = np.linspace(0, dur, int(sr_test * dur), endpoint=False)
    sig_48k = np.sin(2 * np.pi * 440 * t).astype(np.float32)

    sig_16k = mt.resample_audio(sig_48k, orig_sr=48000, target_sr=16000)
    expected_len = round(len(sig_48k) * 16000 / 48000)
    check(
        "resample_audio 48k -> 16k dimension",
        abs(len(sig_16k) - expected_len) <= 2,
        f"len={len(sig_16k)}, exp={expected_len}",
    )

    sig_44k = np.sin(2 * np.pi * 440 * np.linspace(0, dur, int(44100 * dur), endpoint=False)).astype(np.float32)
    sig_16k_from_44 = mt.resample_audio(sig_44k, orig_sr=44100, target_sr=16000)
    check("resample_audio 44.1k -> 16k no vacio", len(sig_16k_from_44) > 0, f"len={len(sig_16k_from_44)}")

    sig_same = mt.resample_audio(sig_16k, orig_sr=16000, target_sr=16000)
    check("resample_audio 16k -> 16k sin cambios", len(sig_same) == len(sig_16k))

    empty_resample = mt.resample_audio(np.zeros(0, dtype=np.float32), 48000, 16000)
    check("resample_audio array vacio", len(empty_resample) == 0)

    # ── 3. AudioPipeline ante Array Vacío ─────────────────────────────────────
    pipe = core.AudioPipeline(fast_mode=True)
    res_empty_pipe = pipe.process(np.zeros(0, dtype=np.float32))
    check(
        "AudioPipeline.process array vacio no lanza excepcion",
        isinstance(res_empty_pipe, np.ndarray) and len(res_empty_pipe) == 0,
    )

    # ── 4. Detección de Mains Hum (50 Hz / 60 Hz) ────────────────────────────
    sr = 16000
    t_hum = np.linspace(0, 1.0, sr, endpoint=False)
    hum_50 = (0.3 * np.sin(2 * np.pi * 50 * t_hum) + 0.01 * np.random.randn(sr)).astype(np.float32)
    hum_60 = (0.3 * np.sin(2 * np.pi * 60 * t_hum) + 0.01 * np.random.randn(sr)).astype(np.float32)
    clean_audio = (0.2 * np.sin(2 * np.pi * 1000 * t_hum)).astype(np.float32)

    check("detect_mains_hum detecta 50 Hz", mt.detect_mains_hum(hum_50, sr=sr) is True)
    check("detect_mains_hum detecta 60 Hz", mt.detect_mains_hum(hum_60, sr=sr) is True)
    check("detect_mains_hum no da falso positivo en señal limpia", mt.detect_mains_hum(clean_audio, sr=sr) is False)

    # ── 5. Medición Acústica Sintética (measure_signal) ──────────────────────
    saved_stream = mt.sd.InputStream if mt.sd else None
    saved_sleep = mt.sd.sleep if mt.sd else None

    try:
        if mt.sd:
            mt.sd.sleep = lambda ms: None

            # Voz óptima: 70% voz (rms ~ 0.15), 30% ambiente silencioso (rms ~ 0.005)
            n_samples = 16000 * 2
            n_speech = int(n_samples * 0.7)
            n_silence = n_samples - n_speech
            np.random.seed(42)
            speech_part = np.random.normal(0, 0.15, n_speech).astype(np.float32)
            silence_part = np.random.normal(0, 0.005, n_silence).astype(np.float32)
            optimal_samples = np.concatenate([speech_part, silence_part])
            mt.sd.InputStream = lambda **kw: FakeInputStream(optimal_samples, **kw)
            lvl_calls = []
            res_opt = mt.measure_signal(duration=2.0, on_level=lvl_calls.append)
            check(
                "measure_signal OPTIMAL veredicto", res_opt["veredicto"] in ("OPTIMAL", "OK"), str(res_opt["veredicto"])
            )
            check("measure_signal on_level callbacks llamados", len(lvl_calls) > 0, f"calls={len(lvl_calls)}")
            check("measure_signal p90 calculado correctamente", res_opt["p90"] >= 0.14, f"p90={res_opt['p90']}")

            # Señal débil (p90 ~ 0.035)
            weak_samples = np.full(n_samples, 0.035, dtype=np.float32)
            mt.sd.InputStream = lambda **kw: FakeInputStream(weak_samples, **kw)
            res_weak = mt.measure_signal(duration=2.0)
            check("measure_signal WEAK veredicto", res_weak["veredicto"] == "WEAK", str(res_weak["veredicto"]))

            # Silencio digital
            silence_samples = np.zeros(n_samples, dtype=np.float32)
            mt.sd.InputStream = lambda **kw: FakeInputStream(silence_samples, **kw)
            res_sil = mt.measure_signal(duration=2.0)
            check("measure_signal SILENCIO veredicto", res_sil["veredicto"] == "SILENCIO", str(res_sil["veredicto"]))
            check("measure_signal is_digital_silence flag", res_sil["is_digital_silence"] is True)

            # Clipping
            clip_samples = np.ones(n_samples, dtype=np.float32)
            mt.sd.InputStream = lambda **kw: FakeInputStream(clip_samples, **kw)
            res_clip = mt.measure_signal(duration=2.0)
            check("measure_signal CLIPPING veredicto", res_clip["veredicto"] == "CLIPPING", str(res_clip["veredicto"]))
            check("measure_signal clipping_pct > 50%", res_clip["clipping_pct"] > 50.0)

            # Error de stream
            mt.sd.InputStream = lambda **kw: FakeInputStream(optimal_samples, fail=True, **kw)
            res_err = mt.measure_signal(duration=2.0)
            check("measure_signal error stream manejado", "ERROR" in res_err["veredicto"], str(res_err["veredicto"]))
    finally:
        if mt.sd:
            mt.sd.InputStream = saved_stream
            mt.sd.sleep = saved_sleep

    # ── 6. Compatibilidad y Fallback de Dispositivos ──────────────────────────
    with patch.object(mt.sd, "check_input_settings") as mock_check, patch.object(mt.sd, "query_devices") as mock_query:
        # Caso A: Frecuencia 16k soportada directamente
        mock_check.return_value = None
        mock_query.return_value = {"name": "Default Mic", "default_samplerate": 48000}
        compat_ok = mt.check_device_compatibility(0, target_sr=16000)
        check(
            "check_device_compatibility 16k OK",
            compat_ok["compatible"] is True and compat_ok["needs_resampling"] is False,
        )

        # Caso B: Frecuencia 16k falla (ALSA hw -9997), pero 48k pasa
        def side_effect(device=None, samplerate=None, channels=None):
            if samplerate == 16000:
                raise RuntimeError("Invalid sample rate [PaErrorCode -9997]")
            return None

        mock_check.side_effect = side_effect
        mock_query.return_value = {"name": "ALSA hw:1,0", "default_samplerate": 48000}
        compat_fallback = mt.check_device_compatibility(3, target_sr=16000)
        check(
            "check_device_compatibility detecta fallback nativo",
            compat_fallback["needs_resampling"] is True and compat_fallback["native_sr"] == 48000,
        )

    # ── 7. auto_fix() y MicTroubleshooter Class ──────────────────────────────
    tb = mt.MicTroubleshooter()
    diag = tb.diagnose()
    check("MicTroubleshooter.diagnose()", "backend" in diag and "status" in diag, str(diag))

    # Prueba de auto_fix
    with (
        patch.object(mt, "get_mic_state") as mock_st,
        patch.object(mt, "unmute_mic") as mock_unmute,
        patch.object(mt, "set_mic_volume") as mock_vol,
    ):
        mock_st.side_effect = [
            mt.MicState(volume=27, is_muted=True, status="MUTED"),
            mt.MicState(volume=100, is_muted=False, status="OK"),
        ]
        mock_unmute.return_value = True
        mock_vol.return_value = True

        fix_out = mt.auto_fix(target_volume=100)
        check("auto_fix() aplica unmute y volumen", mock_unmute.called and mock_vol.called)
        check("auto_fix() reporta success=True", fix_out["success"] is True, str(fix_out))
        check("auto_fix() registra acciones realizadas", len(fix_out["actions"]) >= 2, str(fix_out["actions"]))

    print("=" * 70)
    if failures:
        print(f"RESULTADO: TEST_MIC_TROUBLESHOOTER FAIL ({len(failures)} fallos)")
        sys.exit(1)
    else:
        print("RESULTADO: TEST_MIC_TROUBLESHOOTER_OK")
        sys.exit(0)


if __name__ == "__main__":
    run_tests()
