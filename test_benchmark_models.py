#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_benchmark_models.py — Benchmark reproducible tiny/base/small.

Reutiliza la logica de WER/normalizacion de bench_models.py y el MISMO motor
de la app (LocalWhisperEngine, language="auto") sobre tts_clase.wav.

Blindaje contra el no-determinismo de whisper:
  * tiny y base se transcriben RUNS_ASSERTED=3 veces cada uno.
  * El assert central compara la MEDIANA del WER (robusta a valores atipicos)
    en vez de una sola corrida.
  * El JSON guarda mediana, media, desviacion estandar y las WER individuales
    de cada corrida, para trazar la dispersion real entre ejecuciones.
  * small se transcribe 1 vez (solo datos, no se aserta).

Nota: en esta maquina whisper (temperatura 0, decodificacion greedy) resulto
determinista sobre tts_clase.wav (std=0.00 en 3 corridas); el diseno por
mediana se mantiene como red de seguridad por si otros caminos del pipeline
(VAD, paralelismo, versiones futuras) introducen variacion.

Garantia que valida (y por la que FALLA con exit 1):
    mediana(base) debe superar a mediana(tiny) por al menos MARGIN_PP puntos
    de WER.

La ventaja real medida es ~10 puntos (tiny ~20% vs base ~11%), asi que un
margen de 2 pp deja ~8 pp de colchon frente a la variacion de muestreo.

Si faltan prerequisitos (WAV de referencia, guion o modelos tiny/base en cache
o en models/) el test hace SKIP con exit 0 y un mensaje claro, en vez de
descargar ~500 MB o fallar en maquinas sin los modelos.
"""
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bench_models as bm  # normalizacion/WER/run_model reutilizados

WAV = "tts_clase.wav"
OUT_JSON = "benchmark_results.json"
MARGIN_PP = 2.0  # puntos de WER minimos de ventaja exigidos a base sobre tiny
RUNS_ASSERTED = 3  # corridas por modelo para los modelos asertados (tiny/base)
MODELS = ("tiny", "base", "small")


def _motor_backend():
    """Backend real del motor (faster-whisper u openai-whisper)."""
    try:
        from audioclass_core import LocalWhisperEngine
        return LocalWhisperEngine("tiny").backend
    except Exception:
        return "desconocido"


def _whisper_version():
    """Version de openai-whisper instalada (para trazabilidad del benchmark)."""
    try:
        import whisper
        return getattr(whisper, "__version__", "desconocida")
    except Exception:
        return "no instalado"


def _available_models():
    """Modelos whisper disponibles localmente SIN descargar nada: cache de
    openai-whisper (~/.cache/whisper/*.pt), cache de faster-whisper
    (~/.cache/huggingface, modelos CT2) y models/ del repo."""
    found = set()
    cache = os.path.expanduser("~/.cache/whisper")
    if os.path.isdir(cache):
        for f in os.listdir(cache):
            if f.endswith(".pt"):
                found.add(f[:-3])
    # faster-whisper: modelos CT2 en ~/.cache/huggingface/hub/models--*
    hf = os.path.expanduser("~/.cache/huggingface/hub")
    if os.path.isdir(hf):
        for d in os.listdir(hf):
            for name in ("tiny", "base", "small", "medium"):
                if d.startswith(f"models--Systran--faster-whisper-{name}"):
                    found.add(name)
    repo_models = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    if os.path.isdir(repo_models):
        for f in os.listdir(repo_models):
            if f.endswith(".pt"):
                found.add(f[:-3])
    return found


def _run_once(name, ref, dur):
    """Una transcripcion del modelo y su WER. Devuelve (wer_pct, elapsed_s, res).
    Devuelve None si el modelo transcribio vacio (fallo de carga, no de
    calidad), para que el llamador falle con mensaje claro."""
    res, elapsed = bm.run_model(name)
    text = res.get("text", "") or ""
    if not text.strip():
        return None
    w = bm.wer(ref, bm.normalize(text))
    return w * 100, elapsed, res


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # ── Prerequisitos: si faltan, SKIP limpio (exit 0) ────────────────────────
    missing = []
    if not os.path.exists(WAV):
        missing.append(f"falta {WAV}")
    if not os.path.exists(bm.GUION_PY):
        missing.append(f"falta {bm.GUION_PY}")
    avail = _available_models()
    if not {"tiny", "base"} <= avail:
        missing.append("faltan modelos tiny/base en cache (~/.cache/whisper) o models/")
    if missing:
        print("BENCH_MODELS_SKIP: " + "; ".join(missing))
        print("(ejecuta antes el benchmark una vez para descargar los modelos)")
        return 0

    ref = bm.normalize(bm.load_reference())
    dur = bm.audio_duration(WAV)
    print(f"Guion de referencia: {len(ref)} palabras | audio: {dur:.1f}s | "
          f"modelos disponibles: {sorted(avail)}")

    results = {}
    for name in MODELS:
        runs = RUNS_ASSERTED if name in ("tiny", "base") else 1
        wers, times, metas = [], [], []
        for i in range(runs):
            out = _run_once(name, ref, dur)
            if out is None:
                print(f"BENCH_MODELS_FAIL: {name} transcribio vacio "
                      f"(corrida {i + 1}/{runs})")
                return 1
            w, elapsed, res = out
            wers.append(w)
            times.append(elapsed)
            metas.append(res)
            print(f"  {name} corrida {i + 1}/{runs}: WER {w:5.1f}%  "
                  f"transcribe {elapsed:5.1f}s  idioma {res.get('language')}  "
                  f"chunks {res.get('chunks')}")

        median_w = statistics.median(wers)
        mean_w = statistics.mean(wers)
        std_w = statistics.stdev(wers) if len(wers) > 1 else 0.0
        median_t = statistics.median(times)
        # Metadatos de la corrida con WER mas cercana a la mediana (la mas
        # representativa). min() por diferencia en vez de .index() porque con
        # un numero PAR de corridas statistics.median devuelve el promedio de
        # los dos valores centrales, que puede no estar en la lista (ValueError).
        med_idx = min(range(len(wers)), key=lambda i: abs(wers[i] - median_w))
        res = metas[med_idx]
        results[name] = {
            "wer_median_pct": round(median_w, 2),
            "wer_mean_pct": round(mean_w, 2),
            "wer_std_pct": round(std_w, 2),
            "wer_runs_pct": [round(x, 2) for x in wers],
            "runs": runs,
            "transcribe_s_median": round(median_t, 1),
            "transcribe_s_runs": [round(x, 1) for x in times],
            "x_duration_median": round(median_t / dur, 2),
            "chunks": res.get("chunks"),
            "workers": res.get("workers"),
            "language": res.get("language"),
            "text_len": len(res.get("text", "") or ""),
        }
        print(f"  -> {name}: mediana {median_w:.1f}% | media {mean_w:.1f}% | "
              f"std {std_w:.2f} | runs {[round(x,1) for x in wers]}")

    # ── Guardar resultados (trazabilidad) ─────────────────────────────────────
    record = {
        "audio": WAV,
        "duration_s": round(dur, 1),
        "reference_words": len(ref),
        "margin_pp": MARGIN_PP,
        "runs_asserted": RUNS_ASSERTED,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "whisper_nondeterministic": True,
        "backend": _motor_backend(),
        "std_max_pct": max((r.get("wer_std_pct", 0.0) for r in results.values()), default=0.0),
        "environment": {
            "python": sys.version.split()[0],
            "whisper": _whisper_version(),
            "os": sys.platform,
        },
        "results": results,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"Resultados guardados en {OUT_JSON}")

    # ── Assert central: mediana(base) DEBE superar a mediana(tiny) ───────────
    tiny_med = results["tiny"]["wer_median_pct"]
    base_med = results["base"]["wer_median_pct"]
    tiny_std = results["tiny"]["wer_std_pct"]
    base_std = results["base"]["wer_std_pct"]
    ok = (base_med + MARGIN_PP) < tiny_med
    print(f"\nmediana base ({base_med:.1f}%±{base_std:.1f}) vs mediana tiny "
          f"({tiny_med:.1f}%±{tiny_std:.1f}): "
          f"{'supera ✅' if base_med < tiny_med else 'NO supera ❌'} "
          f"(margen exigido {MARGIN_PP} pp sobre la mediana)")
    print("BENCH_MODELS_OK" if ok else "BENCH_MODELS_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
