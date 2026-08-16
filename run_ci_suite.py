# -*- coding: utf-8 -*-
"""run_ci_suite.py — SUITE ÚNICA de tests del código fuente (AudioClass v9.1).

Es la ÚNICA fuente de verdad de qué tests valida el repo: la consume el CI
(ci.yml, job "tests") y el despliegue (desplegar_produccion.sh, fase [1]).
Ambos ejecutan EXACTAMENTE la misma lista, en el mismo orden, con el mismo
criterio de éxito — así es imposible que una de las dos vías omita un test
o use un patrón distinto (problema histórico: tests que "pasaban" enmascarados
por pipelines o listas divergentes).

Cada entrada es (nombre del test sin .py, patrón de éxito). Los tests GUI
(instancian App()) se envuelven con xvfb-run automáticamente cuando no hay
display (Linux/CI); en Windows el display es nativo y no hace falta.

Uso:
    python -u run_ci_suite.py                 # suite completa (13 tests)
    python -u run_ci_suite.py --skip-benchmark # omite test_benchmark_models (lento)
    python -u run_ci_suite.py --list          # imprime la lista (nombres, 1 por línea)
    python -u run_ci_suite.py <nombre>        # un solo test (pasos nombrados del CI)

Salida por test:  "OK   nombre (Ns)"  /  "FAIL nombre (rc=N, sin patrón ...)"
Resumen final:    "CI_SUITE_OK (13/13)"  /  "CI_SUITE_FAIL (11/13)"
Exit code 0 si TODOS pasan, 1 si alguno falla, 2 si el nombre no existe.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

# ── SUITE ÚNICA: (nombre, patrón de éxito) ────────────────────────────────────
# GUI = instancia App() -> necesita display (xvfb-run en Linux sin DISPLAY).
GUI = frozenset({
    "test_ui_smoke", "test_ui_v91", "test_wcag_contrast",
    "test_privacy_consent", "test_export_docx_pdf", "test_e2e_ui",
})

SUITE = [
    # Rápidos de UI / privacidad / seguridad (fallan pronto si algo se rompe)
    ("test_ui_smoke",          r"SMOKE_OK"),
    ("test_ui_v91",            r"UI_V91 OK|TODO OK"),
    ("test_wcag_contrast",     r"RESULTADO: TODO OK"),
    ("test_privacy_consent",   r"PRIVACY_SMOKE: \d+ OK, 0 fallos"),
    ("test_colab_server_security", r"COLAB_SERVER_SECURITY: \d+ OK, 0 fallos"),
    # Motor y exportación (voz real + modelos)
    ("test_parallel_transcribe", r"ALL_OK"),
    ("test_export_docx_pdf",   r"EXPORT_OK"),
    ("test_e2e_ui",            r"E2E_UI_OK"),
    ("test_stress_transcripcion", r"STRESS_ALL_OK"),
    ("test_mejoras_v10",       r"MEJORAS_V10_OK"),
    ("test_lang_auto",         r"LANG_AUTO_ALL_OK"),
    ("test_watchdog",          r"WATCHDOG_ALL_OK"),
    # Benchmark lento (opcional con --skip-benchmark)
    ("test_benchmark_models",  r"BENCH_MODELS_OK"),
]

# Timeouts por test (s). Observados en 4 corridas del driver (14-ago-2026):
# el único test cerca del tope era el de estrés (217-265s reales vs 300s,
# margen de ~35s) -> se sube a 480s para no dar falso timeout en runners
# lentos. El benchmark (118-183s reales) ya tenía 600s; el resto nunca pasó
# de 68s (default 300s).
TIMEOUTS = {"test_benchmark_models": 600,
            "test_stress_transcripcion": 480}
SKIP_BENCHMARK = "--skip-benchmark" in sys.argv

USE_XVFB = (os.name != "nt"
            and not os.environ.get("DISPLAY")
            and shutil.which("xvfb-run") is not None)


def run_one(name, pattern):
    """Ejecuta un test, devuelve (ok, rc, output, segundos).

    La salida va a un ARCHIVO temporal, no a un pipe: si un test deja un
    proceso hijo reteniendo el stdout, el pipe bloquearía la lectura del
    driver y el timeout no podría interrumpirla en Windows (se observó un
    colgado de ~51 min). Con archivo, el driver solo espera al proceso
    directo y el timeout lo mata de forma fiable.
    """
    args = [sys.executable, "-u", os.path.join(HERE, name + ".py")]
    if USE_XVFB and name in GUI:
        args = ["xvfb-run", "-a"] + args
    tmp = os.path.join(tempfile.gettempdir(), f"_suite_{name}.log")
    t0 = time.time()
    try:
        with open(tmp, "w", encoding="utf-8", errors="replace") as fh:
            p = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT,
                               timeout=TIMEOUTS.get(name, 300))
        # Los tests reconfiguran su stdout a UTF-8; se lee explícitamente en
        # UTF-8 (si no, cp1252 rompe con bytes no imprimibles y el patrón
        # nunca aparece aunque el test pase).
        out = open(tmp, encoding="utf-8", errors="replace").read()
        ok = p.returncode == 0 and re.search(pattern, out) is not None
        return ok, p.returncode, out, time.time() - t0
    except subprocess.TimeoutExpired:
        out = ""
        try:
            out = open(tmp, encoding="utf-8", errors="replace").read()
        except Exception:
            pass
        return False, 124, out, time.time() - t0
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def run_one_test(name, pattern):
    """Corre un test e imprime su línea; devuelve (ok, rc, output, segundos)."""
    ok, rc, out, secs = run_one(name, pattern)
    tail = " ".join(out.strip().splitlines()[-2:])[:100]
    if ok:
        print(f"OK   {name} ({secs:.0f}s)")
    else:
        print(f"FAIL {name} (rc={rc}, {secs:.0f}s, sin patrón {pattern!r}; último: {tail})")
    return ok, rc, out, secs


def main():
    # --list: los nombres de la suite (los pasos nombrados del CI se generan
    # a partir de esta lista y un guard de paridad exige que coincidan).
    if "--list" in sys.argv:
        for name, _ in SUITE:
            print(name)
        return 0
    # <nombre>: un solo test — la ejecución (patrón, timeout, xvfb) sigue
    # viviendo AQUÍ, así el CI no duplica lógica ni criterios de éxito.
    named = [a for a in sys.argv[1:] if not a.startswith("--")]
    if named:
        name = named[0]
        pattern = dict(SUITE).get(name)
        if pattern is None:
            print(f"run_ci_suite.py: test desconocido '{name}' (usa --list)")
            return 2
        ok, _, _, _ = run_one_test(name, pattern)
        print("CI_SUITE_OK (1/1)" if ok else "CI_SUITE_FAIL (0/1)")
        return 0 if ok else 1
    # Suite completa (la usa desplegar_produccion.sh fase [1]).
    suite = [e for e in SUITE if e[0] != "test_benchmark_models"] if SKIP_BENCHMARK \
        else list(SUITE)
    passed = 0
    for name, pattern in suite:
        ok, _, _, _ = run_one_test(name, pattern)
        passed += int(ok)
    summary = f"CI_SUITE_OK ({passed}/{len(suite)})" if passed == len(suite) \
        else f"CI_SUITE_FAIL ({passed}/{len(suite)})"
    print(summary + (" [benchmark omitido]" if SKIP_BENCHMARK else ""))
    return 0 if passed == len(suite) else 1


if __name__ == "__main__":
    sys.exit(main())
