#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validacion headless de grabar_prueba.py con audio sintetico (sin microfono)."""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from scipy.io import wavfile

import audioclass_v91 as m
import grabar_prueba as gp

SR = m.SAMPLE_RATE
DUR = 20
N = SR * DUR
tt = np.arange(N) / SR


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


failures = []


def check(name, cond, detail=""):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        failures.append(name)


# 1) Sintesis con ruido de fondo tipo ventilador
raw = np.clip(synth_speech(0.5) + fan(0.05), -1.0, 1.0).astype(np.float32)
check("sintesis: audio con senal", float(np.max(np.abs(raw))) > 0.1)
check("sintesis: rms no nulo", float(np.sqrt(np.mean(raw ** 2))) > 0.01)

# 2) process_and_save en directorio temporal (mismo codigo que la app)
with tempfile.TemporaryDirectory() as tmp:
    old = m.OUTPUT_DIR
    m.OUTPUT_DIR = tmp
    try:
        rp, pp, limiter = gp.process_and_save(raw)
    finally:
        m.OUTPUT_DIR = old
    check("process_and_save: limiter del perfil devuelto",
          isinstance(limiter, float) and 0 < limiter <= 1.0, f"= {limiter:.3f}")
    check("process_and_save: raw existe", os.path.exists(rp), os.path.basename(rp))
    check("process_and_save: mejorado existe", os.path.exists(pp), os.path.basename(pp))
    check("nombres convencion app", "_raw.wav" in rp and "_mejorado.wav" in pp)

    # 3) analyze() sobre los WAV guardados
    a = gp.analyze(rp, pp)
    for k, v in a.items():
        check(f"analyze[{k}] finito", np.isfinite(v) and v == v, f"= {v:.4g}")
    check("duracion coherente (~20s)", abs(a["d_raw"] - DUR) < 2.0)
    check("mejorado no mas largo que raw*2",
          a["d_pro"] <= a["d_raw"] * 2 + 1.0)
    # El VAD recorta silencio: la duracion baja y el % de tramas en silencio
    # (ruido de fondo) debe caer claramente.
    check("silencio recortado (sil_p < sil_r)",
          a["sil_p"] < a["sil_r"],
          f"silencio {a['sil_r']:.1f}% -> {a['sil_p']:.1f}%")
    check("SNR mejorado positivo (habla > 2x piso)",
          a["speech_p"] > 2.0 * a["floor_p"],
          f"p90 {a['speech_p']:.4f} vs p10 {a['floor_p']:.4f}")
    check("habla conservada (p90 no colapsa)",
          a["speech_p"] > a["speech_r"] * 0.4,
          f"p90 {a['speech_r']:.4f} -> {a['speech_p']:.4f}")
    check("sin clipping (peak <= limiter + margen)",
          a["peak"] <= 1.02, f"peak {a['peak']:.4f}")

    # 4) pipeline procesa sin errores con el perfil por defecto de la app;
    # con use_vad=True la salida debe ser MAS CORTA (silencio recortado).
    pipe = m.AudioPipeline("Clase Universitaria", fast_mode=False, use_vad=True)
    proc = pipe.process(raw)
    check("pipeline: VAD recorta (out <= in, no vacio)",
          len(proc) <= len(raw) and len(proc) > len(raw) * 0.05,
          f"{len(raw)} -> {len(proc)}")

print()
if failures:
    print("RESULTADO: FALLARON", len(failures), ":", ", ".join(failures))
    sys.exit(1)
print("RESULTADO: TODO OK")
