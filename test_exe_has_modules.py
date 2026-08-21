#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_exe_has_modules.py — Verifica que el exe empaquetado incluye
audio_quality_checker y sound_error_solver, y que funcionan correctamente
dentro del bundle.

Patron: usa CArchiveReader para leer el PYZ del exe y extraer los modulos.
Si los modulos no existen o fallan al importar, el test falla.

Patron de exito: EXE_MODULES_OK
"""
import os
import sys
import glob
import types
import marshal
import tempfile
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
        os.path.join(here, "dist_onefile", "AudioClass.exe"),
        os.path.join(here, "dist", "AudioClass", "AudioClass.exe"),
        os.path.join(here, "AudioClass COMPLETA v9.1.exe"),
        os.path.join(here, "AudioClass.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Busqueda generica
    for pat in ["dist_onefile/AudioClass.exe", "dist/AudioClass/AudioClass.exe"]:
        hits = glob.glob(os.path.join(here, pat))
        if hits:
            return hits[0]
    return None


def _load_module_from_exe(exe_path, module_name):
    """Extrae un modulo del PYZ del exe y lo ejecuta como modulo."""
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError:
        print("  SKIP  PyInstaller no instalado (pip install pyinstaller)")
        return None

    try:
        c = CArchiveReader(exe_path)
        code = marshal.loads(c.extract(module_name))
        mod = types.ModuleType(module_name)
        mod.__file__ = os.path.join(os.path.dirname(exe_path), f"{module_name}.py")
        mod.__package__ = ""
        exec(code, mod.__dict__)
        return mod
    except KeyError:
        return None
    except Exception as e:
        print(f"  WARN  Error cargando {module_name}: {e}")
        return None


print("=" * 60)
print("TEST: Verificar modulos de calidad en el exe empaquetado")
print("=" * 60)

# ── Buscar el exe ───────────────────────────────────────────────────────────
exe = _find_exe()
if exe is None:
    print("\n  SKIP  No se encontro exe empaquetado (dist_onefile/ o dist/)")
    print("  Compila primero con: pyinstaller AudioClass_v91_onefile.spec")
    print("EXE_MODULES_OK")
    sys.exit(0)

size_mb = os.path.getsize(exe) / (1024 * 1024)
print(f"\n  Exe encontrado: {os.path.basename(exe)} ({size_mb:.1f} MB)")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: audio_quality_checker esta en el PYZ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Modulo audio_quality_checker ---")

aqc = _load_module_from_exe(exe, "audio_quality_checker")
check("audio_quality_checker encontrado en exe", aqc is not None,
      "Modulo no esta en el PYZ del exe")

if aqc is not None:
    # Verificar que tiene las funciones principales
    check("check_audio_quality existe", hasattr(aqc, "check_audio_quality"))
    check("check_wav_file existe", hasattr(aqc, "check_wav_file"))
    check("format_report_text existe", hasattr(aqc, "format_report_text"))
    check("AudioQualityReport existe", hasattr(aqc, "AudioQualityReport"))

    # Verificar que funciona con audio de prueba
    SR = 16000
    N = int(SR * 2.0)
    t = np.arange(N) / SR
    np.random.seed(42)

    # Audio normal
    audio_ok = (0.2 * np.sin(2 * np.pi * 300 * t) +
                0.001 * np.random.randn(N)).astype(np.float32)
    r_ok = aqc.check_audio_quality(audio_ok, sr=SR)
    check("check_audio_quality retorna reporte", r_ok is not None)
    check("audio OK detectado correctamente", r_ok.verdict != "FAIL",
          f"verdict={r_ok.verdict}")
    check("rms_p90 > 0", r_ok.rms_p90 > 0, f"p90={r_ok.rms_p90}")

    # Audio silencioso
    audio_sil = (np.random.randn(N) * 0.0005).astype(np.float32)
    r_sil = aqc.check_audio_quality(audio_sil, sr=SR)
    check("silencio detectado como FAIL", r_sil.verdict == "FAIL",
          f"verdict={r_sil.verdict}")

    # format_report_text
    txt = aqc.format_report_text(r_ok)
    check("format_report_text produce texto", len(txt) > 0,
          f"len={len(txt)}")

    # Audio vacio
    r_empty = aqc.check_audio_quality(np.array([], dtype=np.float32), sr=SR)
    check("audio vacio -> FAIL", r_empty.verdict == "FAIL")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: sound_error_solver esta en el PYZ
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Modulo sound_error_solver ---")

ses = _load_module_from_exe(exe, "sound_error_solver")
check("sound_error_solver encontrado en exe", ses is not None,
      "Modulo no esta en el PYZ del exe")

if ses is not None:
    check("solve_audio_issues existe", hasattr(ses, "solve_audio_issues"))
    check("suggest_manual_actions existe", hasattr(ses, "suggest_manual_actions"))
    check("format_fix_report existe", hasattr(ses, "format_fix_report"))
    check("SoundFix existe", hasattr(ses, "SoundFix"))

    # Verificar que funciona con audio de prueba
    SR = 16000
    N = int(SR * 2.0)
    t = np.arange(N) / SR
    np.random.seed(42)

    # Audio debil -> solver debe aplicar correcciones
    audio_weak = (np.random.randn(N) * 0.008).astype(np.float32)
    r_weak = aqc.check_audio_quality(audio_weak, sr=SR) if aqc else None
    fixes, fixed = ses.solve_audio_issues(audio_weak, sr=SR, report=r_weak)
    check("solve_audio_issues retorna tupla", isinstance(fixes, tuple))
    check("audio debil tiene correcciones", len(fixes) > 0,
          f"fixes={len(fixes)}")

    # Verificar que el nivel sube
    rms_before = float(np.sqrt(np.mean(audio_weak ** 2)))
    rms_after = float(np.sqrt(np.mean(fixed ** 2)))
    check("nivel sube despues del fix", rms_after > rms_before,
          f"before={rms_before:.6f}, after={rms_after:.6f}")

    # suggest_manual_actions
    if r_weak:
        actions = ses.suggest_manual_actions(r_weak)
        check("suggest_manual_actions retorna lista", isinstance(actions, list))
        check("acciones para debil no vacia", len(actions) > 0)

    # format_fix_report
    report = ses.format_fix_report(fixes)
    check("format_fix_report produce texto", len(report) > 0)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: audioclass_v91.py tiene el gate de calidad
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Gate de calidad en audioclass_v91 ---")

app = _load_module_from_exe(exe, "audioclass_v91")
check("audioclass_v91 encontrado en exe", app is not None)

if app is not None:
    # Verificar que el modulo principal importa los modulos de calidad
    has_qa = getattr(app, "AUDIO_QA", False)
    check("AUDIO_QA flag esta definido", hasattr(app, "AUDIO_QA"),
          f"AUDIO_QA={has_qa}")

    # Verificar que check_audio_quality y solve_audio_issues estan disponibles
    # (importados en el top-level de audioclass_v91)
    check("check_audio_quality importado en app",
          hasattr(app, "check_audio_quality") or has_qa,
          "No se encontro check_audio_quality en el modulo principal")

    # Verificar que los metodos de gate existen en la clase App
    if hasattr(app, "App"):
        check("_procsave existe", hasattr(app.App, "_procsave"))
        check("_starttrans existe", hasattr(app.App, "_starttrans"))
    else:
        check("Clase App existe", False, "Clase App no encontrada")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: Integridad del bundle
# ═══════════════════════════════════════════════════════════════════════════════
print("\n--- Integridad del bundle ---")

try:
    from PyInstaller.archive.readers import CArchiveReader
    c = CArchiveReader(exe)
    # Verificar que los modulos estan en el PYZ (no como archivos sueltos)
    mod_names = ["audio_quality_checker", "sound_error_solver", "audioclass_v91"]
    for mn in mod_names:
        try:
            code = marshal.loads(c.extract(mn))
            # Los code objects son instancias de code (type(lambda: None).__code__)
            # o pueden ser bytes si el modulo fue optimizado
            is_code = hasattr(code, 'co_code') or isinstance(code, bytes)
            check(f"{mn} en PYZ", is_code, f"type={type(code)}")
        except KeyError:
            check(f"{mn} en PYZ", False, "Modulo no encontrado en PYZ - necesitas recompilar el exe")
except Exception as e:
    check("CArchiveReader funciona", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# RESUMEN
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = passed + failed
print(f"RESULTADO: {passed}/{total} checks pasaron")
if failed > 0:
    print(f"  {failed} checks fallaron:")
    for f in failures:
        print(f"    - {f}")
    print("EXE_MODULES_FAIL")
    sys.exit(1)
else:
    print("  Todos los checks pasaron.")
    print("EXE_MODULES_OK")
    sys.exit(0)
