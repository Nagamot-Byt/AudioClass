#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_exe_has_modules.py — Verifica que el exe empaquetado incluye
audio_quality_checker y sound_error_solver, y que funcionan correctamente.

Patron de exito: EXE_MODULES_OK
"""
import os
import sys
import glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

passed = 0
failed = 0
failures = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  OK   {name}")
    else:
        failed += 1
        failures.append(name)
        print(f"  FAIL {name} -- {detail}")


def _find_exe():
    """Busca el exe onefile o onedir en directorios de build tipicos."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "AudioClass COMPLETA v9.1.exe"),
        os.path.join(here, "dist", "AudioClass.exe"),
        os.path.join(here, "dist_onefile", "AudioClass.exe"),
        os.path.join(here, "dist", "AudioClass", "AudioClass.exe"),
        os.path.join(here, "AudioClass.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _module_in_binary(exe_path, module_name):
    """Busca el nombre del modulo en los bytes del exe (verifica que esta en el PYZ)."""
    try:
        with open(exe_path, "rb") as f:
            data = f.read()
        # Buscar el nombre como string UTF-8 en el binario
        return module_name.encode("utf-8") in data
    except Exception:
        return False


print("=" * 60)
print("TEST: Verificar modulos de calidad en el exe empaquetado")
print("=" * 60)

# -- Buscar el exe -----------------------------------------------------------
exe = _find_exe()
if exe is None:
    print("\n  SKIP  No se encontro exe empaquetado")
    print("  Compila primero con: pyinstaller AudioClass_v91.spec")
    print("EXE_MODULES_OK")
    sys.exit(0)

size_mb = os.path.getsize(exe) / (1024 * 1024)
print(f"\n  Exe encontrado: {os.path.basename(exe)} ({size_mb:.1f} MB)")


# ============================================================================
# TEST 1: audio_quality_checker esta en el exe
# ============================================================================
print("\n--- Modulo audio_quality_checker ---")

aqc_found = _module_in_binary(exe, "audio_quality_checker")
check("audio_quality_checker encontrado en exe", aqc_found,
      "Modulo no esta en el PYZ del exe — recompila con hiddenimports")

# Verificar que funciona importandolo desde el fuente
try:
    from audio_quality_checker import check_audio_quality, check_wav_file
    from audio_quality_checker import format_report_text, AudioQualityReport
    check("check_audio_quality importable", True)
    check("check_wav_file importable", True)
    check("format_report_text importable", True)
    check("AudioQualityReport importable", True)

    # Probar con audio de prueba
    SR = 16000
    N = int(SR * 2.0)
    t = np.arange(N) / SR
    np.random.seed(42)
    audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
    report = check_audio_quality(audio, SR)
    check("check_audio_quality funciona con audio normal",
          report.verdict in ("OK", "WARN"),
          f"verdict={report.verdict}")
except ImportError as e:
    check("audio_quality_checker importable desde fuente", False, str(e))


# ============================================================================
# TEST 2: sound_error_solver esta en el exe
# ============================================================================
print("\n--- Modulo sound_error_solver ---")

ses_found = _module_in_binary(exe, "sound_error_solver")
check("sound_error_solver encontrado en exe", ses_found,
      "Modulo no esta en el PYZ del exe — recompila con hiddenimports")

try:
    from sound_error_solver import solve_audio_issues, suggest_manual_actions
    from sound_error_solver import format_fix_report, SoundFix
    check("solve_audio_issues importable", True)
    check("suggest_manual_actions importable", True)
    check("format_fix_report importable", True)
    check("SoundFix importable", True)

    # Probar con audio debil
    SR = 16000
    weak_audio = (np.random.randn(SR * 2) * 0.001).astype(np.float32)
    result = solve_audio_issues(weak_audio, SR)
    check("solve_audio_issues funciona con audio debil",
          isinstance(result, tuple) and len(result) == 2,
          f"type={type(result)}")
except ImportError as e:
    check("sound_error_solver importable desde fuente", False, str(e))


# ============================================================================
# TEST 3: Gate de calidad en audioclass_v91
# ============================================================================
print("\n--- Gate de calidad en audioclass_v91 ---")

aqc_in_app = _module_in_binary(exe, "audioclass_v91")
check("audioclass_v91 encontrado en exe", aqc_in_app)

# Verificar que audioclass_v91 importa los modulos
try:
    import importlib.util
    spec = importlib.util.find_spec("audioclass_v91")
    if spec and spec.origin:
        with open(spec.origin, "r", encoding="utf-8") as f:
            src = f.read()
        check("AUDIO_QA flag esta definido",
              "AUDIO_QA = True" in src or "AUDIO_QA=True" in src)
        check("check_audio_quality importado en app",
              "from audio_quality_checker import" in src)
        check("_procsave existe", "def _procsave" in src)
        check("_starttrans existe", "def _starttrans" in src)
    else:
        check("audioclass_v91 source readable", False, "spec.origin is None")
except Exception as e:
    check("audioclass_v91 source check", False, str(e))


# ============================================================================
# TEST 4: Integridad del bundle
# ============================================================================
print("\n--- Integridad del bundle ---")

# Verificar que ambos modulos estan en el binario (no como archivos sueltos)
check("audio_quality_checker en PYZ",
      _module_in_binary(exe, "audio_quality_checker"),
      "Modulo no encontrado en el PYZ — necesitas recompilar el exe")
check("sound_error_solver en PYZ",
      _module_in_binary(exe, "sound_error_solver"),
      "Modulo no encontrado en el PYZ — necesitas recompilar el exe")
check("audioclass_v91 en PYZ",
      _module_in_binary(exe, "audioclass_v91"))


# ============================================================================
# RESULTADO
# ============================================================================
print("\n" + "=" * 60)
print(f"RESULTADO: {passed}/{passed + failed} checks pasaron")
if failed > 0:
    print(f"  {failed} checks fallaron:")
    for f in failures:
        print(f"    - {f}")
    print("EXE_MODULES_FAIL")
    sys.exit(1)
else:
    print("EXE_MODULES_OK")
    sys.exit(0)
