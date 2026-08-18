#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validacion headless de las mejoras de UI de audioclass_v91.py:
1) metricas de microfono (_mic_metrics) con audio sintetico
2) smoke test de la GUI completa (HOME temporal, sin tocar datos reales)"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# HOME temporal ANTES de importar el modulo (OUTPUT_DIR/CONFIG_PATH se calculan al import)
tmp_home = tempfile.mkdtemp(prefix="ac_ui_home_")
os.environ["HOME"] = tmp_home
os.environ["USERPROFILE"] = tmp_home

import numpy as np
import audioclass_v91 as m

SR = m.SAMPLE_RATE
DUR = 20
N = SR * DUR
tt = np.arange(N) / SR

failures = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


def burst(center, amp, n):
    t = np.arange(n) / SR
    env = np.exp(-((t - 0.1) / 0.05) ** 2)
    return amp * env * np.sin(2 * np.pi * center * t)


def synth_speech(amp=1.0):
    rng = np.random.default_rng(7)
    speech = np.zeros(N)
    pos = 0
    end = SR * 18
    while pos < end:
        n = int(rng.integers(int(0.08 * SR), int(0.25 * SR)))
        seg = (burst(rng.uniform(250, 900), 0.25 * amp, n)
               + burst(rng.uniform(1000, 1600), 0.18 * amp, n)
               + burst(rng.uniform(2000, 2800), 0.12 * amp, n))
        speech[pos:pos + n] += seg[:min(n, N - pos)]
        pos += n + int(rng.integers(int(0.05 * SR), int(0.35 * SR)))
    return speech


def fan(amp):
    rng = np.random.default_rng(3)
    return amp * 0.03 * rng.standard_normal(N)


# ── 1) _mic_metrics con audio sintetico (voz + ventilador) ───────────────────
raw = np.clip(synth_speech(0.5) + fan(0.05), -1.0, 1.0).astype(np.float32)
pipe = m.AudioPipeline("Clase Universitaria", fast_mode=False, use_vad=True)
proc = pipe.process(raw)

# Instancia ligera que solo necesita el atributo .pipeline
fake = type("Fake", (), {"pipeline": pipe})()
metrics = m.App._mic_metrics(fake, raw, proc)
check("_mic_metrics devuelve texto", isinstance(metrics, str) and len(metrics) > 20, repr(metrics[:60]))
check("_mic_metrics: voz detectada (SNR positivo)",
      "[OK] Voz detectada" in metrics and "SNR" in metrics, metrics.splitlines()[0])
check("_mic_metrics: menciona noise gate y limiter",
      "noise gate" in metrics and "limite" in metrics)
for line in metrics.splitlines():
    check(f"_mic_metrics linea finita: {line[:40]}",
          "nan" not in line.lower() and "inf" not in line.lower())

# Audio solo ruido -> debe decir voz muy baja sin crashear
raw_noise = np.clip(fan(0.05), -1.0, 1.0).astype(np.float32)
metrics_n = m.App._mic_metrics(fake, raw_noise, pipe.process(raw_noise))
check("_mic_metrics: solo-ruido -> aviso sin crashear",
      "[!]" in metrics_n or "Voz muy baja" in metrics_n, metrics_n.splitlines()[0])

# Audio vacio -> sin crashear
metrics_e = m.App._mic_metrics(fake, np.zeros(0, np.float32), np.zeros(0, np.float32))
check("_mic_metrics: audio vacio sin crashear",
      isinstance(metrics_e, str) and len(metrics_e) > 0, repr(metrics_e))

# ── 2) Smoke test GUI: App completa con HOME temporal, first_run=False ──────
cfg = m.DEFAULT_CONFIG.copy()
cfg["first_run"] = False
cfg["modo_guiado"] = True
m.save_config(cfg)

gui_ok = False
gui_err = ""
try:
    app = m.App()
    app.update()  # procesa eventos sin entrar en mainloop eterno

    # Metodos nuevos existen y son invocables
    check("_test_mic existe", hasattr(app, "_test_mic"))
    check("_open_output_dir existe", hasattr(app, "_open_output_dir"))
    check("_mic_metrics existe", hasattr(app, "_mic_metrics"))

    # Pilulas de pasos: los 4 labels existen
    check("step_lbls = 4 pasos", len(getattr(app, "step_lbls", {})) == 4)
    app._set_step(2)
    check("_set_step(2) sin errores", True)

    # Abrir la ventana de prueba de microfono (solo crear widgets, no grabar)
    app._test_mic()
    app.update()
    top = getattr(app, "mic_test_top", None)
    check("ventana _test_mic creada", top is not None and top.winfo_exists())

    # Handler del nivel en vivo con la cola (simular mensaje del hilo)
    app.q.put(("mic_lvl", 0.05))
    app.q.put(("mic_result", metrics))
    app._poll()
    check("_poll procesa mic_lvl/mic_result sin errores", True)

    if top is not None:
        top.destroy()
    app.destroy()
    gui_ok = True
except Exception as e:
    import traceback
    gui_err = f"{e}\n{traceback.format_exc()}"

check("smoke GUI completo (App + widgets nuevos)", gui_ok, gui_err[:200] if gui_err else "")

print()
if failures:
    print("RESULTADO: FALLARON", len(failures), ":", ", ".join(failures))
    sys.exit(1)
print("RESULTADO: TODO OK")
# Salir con os._exit (no sys.exit): en Linux, la destruccion estatica C++ de
# libtorch (modelo cargado en el thread daemon del motor local) aborta el
# proceso al apagar el interprete (SIGABRT, rc=134) aun habiendo pasado todos
# los checks. Se vacian los buffers antes para que el driver lea la salida
# completa del archivo de log.
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
