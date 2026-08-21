#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_audio_quality_solver.py — Tests para audio_quality_checker y sound_error_solver
=====================================================================================
Valida:
  - check_audio_quality(): deteccion de problemas y veredictos correctos
  - check_wav_file(): lectura de archivos WAV
  - solve_audio_issues(): correcciones automaticas
  - suggest_manual_actions(): acciones manuales por problema
  - format_report_text() / format_fix_report(): formato legible
"""

import sys, os, traceback
import numpy as np

# Agregar directorio al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audio_quality_checker import (
    check_audio_quality, check_wav_file, format_report_text,
    AudioQualityReport, RMS_SILENCE, RMS_DEBIL, RMS_OK,
)
from sound_error_solver import (
    solve_audio_issues, suggest_manual_actions, format_fix_report,
    SoundFix, _apply_gain, _normalize_clipping, _trim_silence,
)

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} -- {detail}")


print("=" * 60)
print("TESTS: audio_quality_checker + sound_error_solver")
print("=" * 60)

# ── Generar audio de prueba ────────────────────────────────────────────────
SR = 16000
DUR = 3.0
N = int(SR * DUR)
t = np.arange(N) / SR

# Audio normal (voz simulada: tono 300Hz fuerte + ruido muy suave)
# Se usa nivel alto para que el SNR sea bueno y pase como OK
np.random.seed(42)
audio_normal = (0.2 * np.sin(2 * np.pi * 300 * t) +
                0.1 * np.sin(2 * np.pi * 800 * t) +
                0.001 * np.random.randn(N)).astype(np.float32)

# Audio silencioso
audio_silence = (np.random.randn(N) * 0.001).astype(np.float32)

# Audio muy debil
audio_weak = (np.random.randn(N) * 0.008).astype(np.float32)

# Audio con clipping
audio_clip = np.clip(audio_normal * 5.0, -1.0, 1.0).astype(np.float32)

# Audio vacio
audio_empty = np.array([], dtype=np.float32)

# Audio corto
audio_short = (np.sin(2 * np.pi * 300 * np.arange(int(SR * 0.5)) / SR) * 0.1).astype(np.float32)

# Audio con mucho silencio
audio_mostly_silence = np.zeros(N, dtype=np.float32)
audio_mostly_silence[1000:2000] = 0.05 * np.sin(2 * np.pi * 300 * np.arange(1000) / SR)


# ── Tests de audio_quality_checker ──────────────────────────────────────────
print("\n--- check_audio_quality ---")

r_normal = check_audio_quality(audio_normal, sr=SR)
check("normal -> OK o WARN (no FAIL)", r_normal.verdict != "FAIL",
      f"verdict={r_normal.verdict}, issues={r_normal.issues}")
check("normal p90 > 0", r_normal.rms_p90 > 0.0, f"p90={r_normal.rms_p90}")
check("normal peak > 0", r_normal.peak > 0.0, f"peak={r_normal.peak}")

r_silence = check_audio_quality(audio_silence, sr=SR)
check("silencio -> FAIL o WARN", r_silence.verdict in ("FAIL", "WARN"),
      f"verdict={r_silence.verdict}")
check("silencio tiene issue 'silence' o 'too_quiet'",
      "silence" in r_silence.issues or "too_quiet" in r_silence.issues,
      f"issues={r_silence.issues}")

r_weak = check_audio_quality(audio_weak, sr=SR)
check("audio debil -> FAIL o WARN", r_weak.verdict in ("FAIL", "WARN"),
      f"verdict={r_weak.verdict}")
check("audio debil tiene issue", len(r_weak.issues) > 0, f"issues={r_weak.issues}")
check("audio debil auto_fixable", r_weak.auto_fixable, f"auto_fixable={r_weak.auto_fixable}")

r_clip = check_audio_quality(audio_clip, sr=SR)
check("clipping detectado", r_clip.clipping_pct > 0, f"clipping={r_clip.clipping_pct}")
check("clipping issue", "clipping" in r_clip.issues, f"issues={r_clip.issues}")

r_empty = check_audio_quality(audio_empty, sr=SR)
check("vacio -> FAIL", r_empty.verdict == "FAIL", f"verdict={r_empty.verdict}")
check("vacio tiene issue 'empty'", "empty" in r_empty.issues, f"issues={r_empty.issues}")

r_short = check_audio_quality(audio_short, sr=SR)
check("muy corto -> FAIL", r_short.verdict == "FAIL", f"verdict={r_short.verdict}")
check("muy corto issue 'too_short'", "too_short" in r_short.issues, f"issues={r_short.issues}")

r_mute = check_audio_quality(audio_mostly_silence, sr=SR)
check("mayormente silencio -> WARN o FAIL", r_mute.verdict in ("WARN", "FAIL"),
      f"verdict={r_mute.verdict}")
check("silence_ratio > 0.5", r_mute.silence_ratio > 0.5,
      f"silence_ratio={r_mute.silence_ratio}")


# ── format_report_text ──────────────────────────────────────────────────────
print("\n--- format_report_text ---")

txt = format_report_text(r_normal)
check("reporte contiene veredicto", "[OK]" in txt or "[WARN]" in txt,
      f"txt={txt[:100]}")
check("reporte contiene p90", "p90" in txt)
check("reporte contiene SNR", "SNR" in txt)

txt_fail = format_report_text(r_empty)
check("reporte FAIL contiene mensaje", "FAIL" in txt_fail)


# ── Tests de sound_error_solver ─────────────────────────────────────────────
print("\n--- solve_audio_issues ---")

fixes_normal, fixed_normal = solve_audio_issues(audio_normal, sr=SR)
check("normal audio sin cambio significativo",
      np.max(np.abs(fixed_normal - audio_normal)) < 0.05,
      f"max_diff={np.max(np.abs(fixed_normal - audio_normal))}")

fixes_clip, fixed_clip = solve_audio_issues(audio_clip, sr=SR)
check("clipping tiene correccion", len(fixes_clip) > 0, f"fixes={len(fixes_clip)}")
check("clipping pico reducido", float(np.max(np.abs(fixed_clip))) <= 1.0,
      f"peak={np.max(np.abs(fixed_clip))}")

fixes_weak, fixed_weak = solve_audio_issues(audio_weak, sr=SR)
check("audio debil tiene correccion", len(fixes_weak) > 0, f"fixes={len(fixes_weak)}")
# El audio debil debe tener mayor nivel despues
rms_before = float(np.sqrt(np.mean(audio_weak ** 2)))
rms_after = float(np.sqrt(np.mean(fixed_weak ** 2)))
check("audio debil nivel sube", rms_after > rms_before,
      f"before={rms_before:.6f}, after={rms_after:.6f}")

# Test con reporte pre-calculado
fixes_with_report, _ = solve_audio_issues(audio_weak, sr=SR, report=r_weak)
check("solve con reporte pre-calculado", len(fixes_with_report) > 0,
      f"fixes={len(fixes_with_report)}")


# ── _apply_gain ─────────────────────────────────────────────────────────────
print("\n--- _apply_gain ---")

gained = _apply_gain(audio_weak, target_rms=0.12)
rms_gained = float(np.sqrt(np.mean(gained ** 2)))
check("gain boost sube nivel", rms_gained > float(np.sqrt(np.mean(audio_weak ** 2))),
      f"rms={rms_gained:.6f}")
check("gain clipa a 1.0", np.max(np.abs(gained)) <= 1.0,
      f"peak={np.max(np.abs(gained))}")

silence_gained = _apply_gain(audio_silence, target_rms=0.12)
# Con silencio digital (rms ~0.001), el gain se limita a 10x
# y el resultado queda en ~0.01, que es aceptable
rms_sil = float(np.sqrt(np.mean(silence_gained ** 2)))
check("gain en silencio no excede limite",
      rms_sil < 0.15,
      f"rms={rms_sil:.6f}")


# ── _normalize_clipping ────────────────────────────────────────────────────
print("\n--- _normalize_clipping ---")

normed = _normalize_clipping(audio_clip)
peak_normed = float(np.max(np.abs(normed)))
check("normalize reduce peak", peak_normed <= 0.96, f"peak={peak_normed:.4f}")

# Audio con pico <= 0.95 no debe cambiar
audio_safe = np.clip(audio_normal, -0.9, 0.9).astype(np.float32)
already_ok = _normalize_clipping(audio_safe)
check("normalize audio seguro no cambia",
      np.allclose(already_ok, audio_safe, atol=1e-6),
      f"max_diff={np.max(np.abs(already_ok - audio_safe)):.6f}")


# ── _trim_silence ───────────────────────────────────────────────────────────
print("\n--- _trim_silence ---")

trimmed = _trim_silence(audio_mostly_silence, sr=SR, threshold=0.01)
check("trim reduce longitud", len(trimmed) < len(audio_mostly_silence),
      f"before={len(audio_mostly_silence)}, after={len(trimmed)}")

trimmed_normal = _trim_silence(audio_normal, sr=SR, threshold=RMS_SILENCE)
check("trim audio normal mantiene longitud similar",
      len(trimmed_normal) >= len(audio_normal) * 0.8,
      f"before={len(audio_normal)}, after={len(trimmed_normal)}")


# ── suggest_manual_actions ──────────────────────────────────────────────────
print("\n--- suggest_manual_actions ---")

actions_silence = suggest_manual_actions(r_silence)
check("acciones para silencio no vacia", len(actions_silence) > 0)
check("acciones para silencio menciona Windows",
      any("Windows" in a for a in actions_silence),
      f"actions={actions_silence[:2]}")

actions_weak = suggest_manual_actions(r_weak)
check("acciones para debil no vacia", len(actions_weak) > 0)
check("acciones para debil menciona ganancia",
      any("ganancia" in a.lower() or "Ganancia" in a for a in actions_weak))

actions_ok = suggest_manual_actions(r_normal)
check("acciones para audio OK son validas",
      len(actions_ok) > 0,
      f"actions={actions_ok}")


# ── format_fix_report ───────────────────────────────────────────────────────
print("\n--- format_fix_report ---")

fix_report = format_fix_report([])
check("sin fixes: mensaje vacio", "No se aplicaron" in fix_report)

fix_report2 = format_fix_report(fixes_clip)
check("con fixes: muestra correcciones", "Correcciones" in fix_report2)


# ── Tests de integracion: WAV file ──────────────────────────────────────────
print("\n--- check_wav_file ---")

# Crear WAV temporal
from scipy.io import wavfile
wav_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_qa.wav")
wavfile.write(wav_path, SR, np.int16(np.clip(audio_normal, -1.0, 1.0) * 32767))
r_wav = check_wav_file(wav_path, sr=SR)
check("WAV file -> OK o WARN", r_wav.verdict in ("OK", "WARN"),
      f"verdict={r_wav.verdict}")
check("WAV duration > 0", r_wav.duration_s > 0, f"dur={r_wav.duration_s}")

# WAV silencioso
wav_silence = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_test_qa_silence.wav")
wavfile.write(wav_silence, SR, np.int16(np.zeros(N, dtype=np.int16)))
r_wav_sil = check_wav_file(wav_silence, sr=SR)
check("WAV silencio -> FAIL", r_wav_sil.verdict == "FAIL", f"verdict={r_wav_sil.verdict}")

# Archivo inexistente
r_wav_bad = check_wav_file("_no_existe.wav", sr=SR)
check("WAV inexistente -> FAIL", r_wav_bad.verdict == "FAIL")

# Limpiar temporales
for f in [wav_path, wav_silence]:
    try:
        os.remove(f)
    except Exception:
        pass


# ── Tests de integracion: SoundFix dataclass ────────────────────────────────
print("\n--- SoundFix dataclass ---")

sf = SoundFix(name="test", description="Test fix", before=0.01, after=0.1, unit="rms_p90")
check("SoundFix attributes", sf.name == "test" and sf.before == 0.01)
check("SoundFix success default", sf.success is True)


# ── Tests edge cases ────────────────────────────────────────────────────────
print("\n--- Edge cases ---")

# Audio mono float64
audio_f64 = audio_normal.astype(np.float64)
r_f64 = check_audio_quality(audio_f64, sr=SR)
check("float64 funciona igual (no FAIL)", r_f64.verdict != "FAIL")

# Audio con un solo sample
audio_one = np.array([0.5], dtype=np.float32)
r_one = check_audio_quality(audio_one, sr=SR)
check("un sample -> FAIL (muy corto)", r_one.verdict == "FAIL")

# Audio None
r_none = check_audio_quality(None, sr=SR)
check("None -> FAIL", r_none.verdict == "FAIL")


# ── RESUMEN ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
total = passed + failed
print(f"RESULTADO: {passed}/{total} tests pasaron")
if failed > 0:
    print(f"  {failed} tests fallaron")
    sys.exit(1)
else:
    print("  Todos los tests pasaron.")
    sys.exit(0)
