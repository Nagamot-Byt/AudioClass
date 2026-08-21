#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_quality_gate_e2e.py — Test E2E del gate de calidad de audio
================================================================
Simula diferentes escenarios de audio (silencio, debil, clipping, normal)
y verifica que:
  1. El quality checker detecta correctamente cada caso
  2. El sound solver aplica las correcciones adecuadas
  3. El gate de calidad en _starttrans bloquea transcripcion en FAIL
  4. El gate permite continuar en WARN con advertencia
  5. El flujo completo _procsave aplica auto-fix y re-procesa

Patron: test standalone con check() como los demas tests del repo.
"""
import os, sys, tempfile, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scipy.io import wavfile

from audio_quality_checker import (
    check_audio_quality, check_wav_file, format_report_text,
    RMS_SILENCE, RMS_DEBIL, RMS_OK,
)
from sound_error_solver import (
    solve_audio_issues, suggest_manual_actions, format_fix_report,
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
print("TEST E2E: Gate de calidad de audio")
print("=" * 60)

SR = 16000
N = int(SR * 3.0)  # 3 segundos
t = np.arange(N) / SR
np.random.seed(42)

# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 1: Audio silencioso -> FAIL -> transcripcion bloqueada
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 1: Silencio digital -> FAIL ---")

audio_silence = (np.random.randn(N) * 0.0005).astype(np.float32)
r_silence = check_audio_quality(audio_silence, sr=SR)

check("silencio detectado como FAIL", r_silence.verdict == "FAIL",
      f"verdict={r_silence.verdict}")
check("silencio tiene issue 'silence'", "silence" in r_silence.issues,
      f"issues={r_silence.issues}")
check("silencio NO es auto_fixable", not r_silence.auto_fixable,
      f"auto_fixable={r_silence.auto_fixable}")
check("silencio severity es error", r_silence.severity == "error",
      f"severity={r_silence.severity}")

# Verificar que el solver no puede corregir silencio total
fixes_silence, fixed_silence = solve_audio_issues(audio_silence, sr=SR, report=r_silence)
check("solver sin correcciones para silencio", len(fixes_silence) == 0,
      f"fixes={len(fixes_silence)}")

# Verificar acciones manuales
actions_silence = suggest_manual_actions(r_silence)
check("acciones manuales para silencio mencionan Windows",
      any("Windows" in a for a in actions_silence))

# Simular gate de _starttrans: WAV silencioso debe bloquear
wav_silence = os.path.join(tempfile.gettempdir(), "_test_gate_silence.wav")
wavfile.write(wav_silence, SR, np.int16(np.clip(audio_silence, -1.0, 1.0) * 32767))
r_wav_sil = check_wav_file(wav_silence, sr=SR)
check("WAV silencio -> FAIL (gate bloquea)", r_wav_sil.verdict == "FAIL",
      f"verdict={r_wav_sil.verdict}")
check("WAV silencio message contiene 'insuficiente'",
      "insuficiente" in r_wav_sil.message.lower() or "silencio" in r_wav_sil.message.lower(),
      f"message={r_wav_sil.message[:80]}")


# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 2: Audio muy debil -> WARN -> gate advierte pero permite
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 2: Audio debil -> WARN ---")

audio_weak = (np.random.randn(N) * 0.008).astype(np.float32)
r_weak = check_audio_quality(audio_weak, sr=SR)

check("audio debil detectado como WARN o FAIL", r_weak.verdict in ("WARN", "FAIL"),
      f"verdict={r_weak.verdict}")
check("audio debil tiene issues", len(r_weak.issues) > 0,
      f"issues={r_weak.issues}")
check("audio debil es auto_fixable", r_weak.auto_fixable,
      f"auto_fixable={r_weak.auto_fixable}")

# Verificar que el solver PUEDE corregir audio debil
fixes_weak, fixed_weak = solve_audio_issues(audio_weak, sr=SR, report=r_weak)
check("solver aplica correcciones a audio debil", len(fixes_weak) > 0,
      f"fixes={len(fixes_weak)}")

# Verificar que el nivel sube despues del fix
rms_before = float(np.sqrt(np.mean(audio_weak ** 2)))
rms_after = float(np.sqrt(np.mean(fixed_weak ** 2)))
check("nivel sube despues del fix", rms_after > rms_before,
      f"before={rms_before:.6f}, after={rms_after:.6f}")

# Verificar acciones manuales
actions_weak = suggest_manual_actions(r_weak)
check("acciones manuales para debil mencionan ganancia",
      any("ganancia" in a.lower() or "Ganancia" in a for a in actions_weak))

# Simular gate de _starttrans: WAV debil -> WARN (no bloquea)
wav_weak = os.path.join(tempfile.gettempdir(), "_test_gate_weak.wav")
wavfile.write(wav_weak, SR, np.int16(np.clip(audio_weak, -1.0, 1.0) * 32767))
r_wav_weak = check_wav_file(wav_weak, sr=SR)
check("WAV debil -> WARN o FAIL (gate advierte)", r_wav_weak.verdict in ("WARN", "FAIL"),
      f"verdict={r_wav_weak.verdict}")


# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 3: Audio con clipping -> WARN -> solver corrige
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 3: Clipping -> solver corrige ---")

audio_clip = np.clip(
    (0.2 * np.sin(2 * np.pi * 300 * t) + 0.1 * np.sin(2 * np.pi * 800 * t)) * 5.0,
    -1.0, 1.0
).astype(np.float32)
r_clip = check_audio_quality(audio_clip, sr=SR)

check("clipping detectado", r_clip.clipping_pct > 0,
      f"clipping={r_clip.clipping_pct}")
check("clipping tiene issue", "clipping" in r_clip.issues,
      f"issues={r_clip.issues}")

# Solver debe normalizar clipping
fixes_clip, fixed_clip = solve_audio_issues(audio_clip, sr=SR, report=r_clip)
check("solver corrige clipping", len(fixes_clip) > 0,
      f"fixes={len(fixes_clip)}")
check("pico reducido post-fix", float(np.max(np.abs(fixed_clip))) <= 1.0,
      f"peak={np.max(np.abs(fixed_clip))}")

# Verificar que el fix reporta bien
fix_text = format_fix_report(fixes_clip)
check("fix report contiene normalizacion", "Normalizado" in fix_text or "normaliz" in fix_text.lower(),
      f"text={fix_text[:100]}")


# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 4: Audio normal -> OK -> gate permite transcripcion
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 4: Audio normal -> OK ---")

audio_normal = (0.2 * np.sin(2 * np.pi * 300 * t) +
                0.1 * np.sin(2 * np.pi * 800 * t) +
                0.001 * np.random.randn(N)).astype(np.float32)
r_normal = check_audio_quality(audio_normal, sr=SR)

check("audio normal no es FAIL", r_normal.verdict != "FAIL",
      f"verdict={r_normal.verdict}")
check("audio normal p90 > 0.05", r_normal.rms_p90 > 0.05,
      f"p90={r_normal.rms_p90}")

# Solver no debe cambiar audio normal significativamente
fixes_normal, fixed_normal = solve_audio_issues(audio_normal, sr=SR, report=r_normal)
check("solver no cambia audio normal", np.max(np.abs(fixed_normal - audio_normal)) < 0.05,
      f"max_diff={np.max(np.abs(fixed_normal - audio_normal))}")

# WAV file check
wav_normal = os.path.join(tempfile.gettempdir(), "_test_gate_normal.wav")
wavfile.write(wav_normal, SR, np.int16(np.clip(audio_normal, -1.0, 1.0) * 32767))
r_wav_normal = check_wav_file(wav_normal, sr=SR)
check("WAV normal -> OK o WARN (gate permite)", r_wav_normal.verdict in ("OK", "WARN"),
      f"verdict={r_wav_normal.verdict}")


# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 5: Flujo completo _procsave con auto-fix
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 5: Flujo _procsave con auto-fix ---")

# Simular audio debil que el solver corrige
audio_to_fix = (np.random.randn(N) * 0.008).astype(np.float32)
r_to_fix = check_audio_quality(audio_to_fix, sr=SR)

# Paso 1: check calidad
check("procsave: calidad detectada", r_to_fix.verdict != "OK",
      f"verdict={r_to_fix.verdict}")

# Paso 2: solver aplica fixes
fixes, fixed = solve_audio_issues(audio_to_fix, sr=SR, report=r_to_fix)
check("procsave: fixes aplicados", len(fixes) > 0,
      f"fixes={len(fixes)}")

# Paso 3: audio corregido tiene mejor nivel
rms_orig = float(np.sqrt(np.mean(audio_to_fix ** 2)))
rms_fixed = float(np.sqrt(np.mean(fixed ** 2)))
check("procsave: nivel mejorado", rms_fixed > rms_orig,
      f"orig={rms_orig:.6f}, fixed={rms_fixed:.6f}")

# Paso 4: re-check post-fix mejora
r_post = check_audio_quality(fixed, sr=SR)
check("procsave: post-fix mejor veredicto",
      r_post.verdict == "OK" or r_post.verdict == "WARN",
      f"verdict={r_post.verdict}")


# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 6: Audio vacio y muy corto -> FAIL rapido
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 6: Edge cases -> FAIL ---")

r_empty = check_audio_quality(np.array([], dtype=np.float32), sr=SR)
check("vacio -> FAIL", r_empty.verdict == "FAIL")
check("vacio severity error", r_empty.severity == "error")

audio_short = (np.sin(2 * np.pi * 300 * np.arange(int(SR * 0.3)) / SR) * 0.1).astype(np.float32)
r_short = check_audio_quality(audio_short, sr=SR)
check("muy corto -> FAIL", r_short.verdict == "FAIL")
check("muy corto issue 'too_short'", "too_short" in r_short.issues)

r_none = check_audio_quality(None, sr=SR)
check("None -> FAIL", r_none.verdict == "FAIL")


# ═══════════════════════════════════════════════════════════════════════════════
# ESCENARIO 7: format_report_text produce output legible
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Escenario 7: Reportes formateados ---")

txt_fail = format_report_text(r_silence)
check("reporte FAIL contiene '[FAIL]'",
      "[FAIL]" in txt_fail, f"txt={txt_fail[:80]}")
check("reporte FAIL contiene 'p90'",
      "p90" in txt_fail)

txt_warn = format_report_text(r_weak)
check("reporte WARN contiene '[WARN]'",
      "[WARN]" in txt_warn, f"txt={txt_warn[:80]}")

txt_ok = format_report_text(r_normal)
check("reporte OK contiene '[OK]' o '[WARN]'",
      "[OK]" in txt_ok or "[WARN]" in txt_ok)


# ═══════════════════════════════════════════════════════════════════════════════
# LIMPIEZA
# ═══════════════════════════════════════════════════════════════════════════════
for f in [wav_silence, wav_weak, wav_normal]:
    try:
        os.remove(f)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = passed + failed
print(f"RESULTADO: {passed}/{total} checks pasaron")
if failed > 0:
    print(f"  {failed} checks fallaron")
    print("QUALITY_GATE_E2E_FAIL")
    sys.exit(1)
else:
    print("  Todos los checks pasaron.")
    print("QUALITY_GATE_E2E_OK")
    sys.exit(0)
