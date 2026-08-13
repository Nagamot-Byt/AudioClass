# -*- coding: utf-8 -*-
"""test_transcribe_headless.py — Regresión del cuelgue/fallo de la transcripción local.

Replica el bug reportado por el usuario (audio de 30s con la barra clavada en
~98% durante horas) y su causa raíz confirmada en los logs:

  R1  CRASH tqdm: la app llamaba a whisper con verbose=False, y whisper
      20250625 ACTIVA una barra tqdm que escribe a sys.stdout. En el exe
      compilado con console=False (o pythonw), sys.stdout es None y tqdm
      reventaba con AttributeError ('NoneType' object has no attribute
      'write') -> la transcripcion local fallaba al instante.
      -> Este test simula la condicion del exe: sys.stdout/sys.stderr = None
         y verifica que transcribe COMPLETA sin excepcion.

  R2  CHUNKING: un audio de 30s generaba 2 chunks (30s + cola de 2s por el
      overlap), forzando el camino paralelo con un chunk casi vacio.
      -> Este test verifica 30s -> 1 chunk (secuencial, mas rapido) y que el
         audio de 100s sigue generando los 4 chunks esperados (paralelo real).

  R3  TIEMPOS: la transcripcion debe terminar en un tiempo acorde a la
      duracion del audio (tope generoso: < 5x la duracion en esta maquina).

  R4  SIN HUECO: el progreso llega a 100% (el ultimo callback = 1.0) y es
      monotonico.
"""
import os, sys, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from scipy.io import wavfile
import audioclass_core as core

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(BASE, "models", "tiny.pt")


def _speech_like(dur, seed=3):
    """Envoltura tipo silabas sobre ruido rosa: forma de voz para whisper."""
    rng = np.random.default_rng(seed)
    n = int(core.SAMPLE_RATE * dur)
    t = np.arange(n) / core.SAMPLE_RATE
    pink = rng.standard_normal(n)
    for k in range(1, 20):
        pink += rng.standard_normal(n) * (1.0 / k)
    pink /= np.std(pink)
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t + 1.3)
    env *= (1.0 - 0.85 * (np.sin(2 * np.pi * 1.25 * t) > 0.55).astype(float))
    sig = pink * env + 0.3 * np.sin(2 * np.pi * 120 * t) * env
    return (sig * 0.5).astype(np.float32)


def _wav(dur):
    p = os.path.join(tempfile.gettempdir(), f"ac_headless_{dur}s.wav")
    wavfile.write(p, core.SAMPLE_RATE, np.int16(np.clip(_speech_like(dur), -1, 1) * 32767))
    return p


def _engine():
    # backend="openai": este test parchea _resolve_model con una ruta .pt y
    # valida el camino del EXE compilado (openai-whisper). El camino faster-
    # whisper se valida en test_mejoras_v10.py.
    eng = core.LocalWhisperEngine("tiny", backend="openai")
    eng._resolve_model = lambda: MODEL
    return eng


def test_chunking():
    eng = _engine()
    # 30s -> exactamente 1 chunk (antes: 2 con la cola redundante de 2s)
    res = eng.transcribe(_wav(30), timestamps=False, progress_callback=lambda *a: None)
    assert res.get("chunks") == 1, f"30s deberia dar 1 chunk, dio {res.get('chunks')}"
    assert res.get("workers") == 1, "1 chunk debe ir por el camino secuencial"
    # 100s -> 4 chunks (paralelo real)
    res = eng.transcribe(_wav(100), timestamps=False, progress_callback=lambda *a: None)
    assert res.get("chunks") == 4, f"100s deberia dar 4 chunks, dio {res.get('chunks')}"
    assert res.get("workers", 1) > 1, ">=2 chunks debe ir por el camino paralelo"
    print(f"R2 OK  chunking: 30s->1 chunk (secuencial), 100s->4 chunks ({res.get('workers')} workers)")


def test_headless_single_chunk():
    """R1+R3+R4: condicion del exe (stdout/stderr None) + tiempo acorde + 100%."""
    path = _wav(30)
    dur = len(wavfile.read(path)[1]) / core.SAMPLE_RATE
    eng = _engine()
    calls = []

    def cb(frac, total, msg):
        calls.append(frac / total if total else 0.0)

    # ── SIMULA EL EXE SIN CONSOLA ──
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout = None
    sys.stderr = None
    try:
        t0 = time.time()
        try:
            res = eng.transcribe(path, timestamps=True, progress_callback=cb)
        except Exception as e:
            raise AssertionError(
                f"transcribe con stdout=None revento (bug tqdm/whisper): {e!r}")
        elapsed = time.time() - t0
    finally:
        sys.stdout, sys.stderr = real_out, real_err

    assert not res.get("error"), res
    assert not res.get("cancelled"), res
    assert res.get("chunks") == 1, res
    assert elapsed < dur * 5, f"30s de audio tardaron {elapsed:.0f}s (>5x duracion)"
    assert calls, "sin callbacks de progreso"
    assert calls[-1] >= 0.99, f"el progreso no llego al 100% (ultimo {calls[-1]:.2f})"
    assert all(b >= a for a, b in zip(calls, calls[1:])), "progreso no monotonico"
    print(f"R1+R3+R4 OK  30s headless (stdout=None) en {elapsed:.1f}s | "
          f"monotonico={all(b >= a for a, b in zip(calls, calls[1:]))} | "
          f"100%={calls[-1]:.2f} | {len(calls)} callbacks")


def test_headless_parallel():
    """R1+R3 en el camino paralelo (100s -> 4 chunks) con stdout=None."""
    path = _wav(100)
    dur = len(wavfile.read(path)[1]) / core.SAMPLE_RATE
    eng = _engine()
    calls = []

    def cb(frac, total, msg):
        calls.append(frac / total if total else 0.0)

    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout = None
    sys.stderr = None
    try:
        t0 = time.time()
        try:
            res = eng.transcribe(path, timestamps=False, progress_callback=cb)
        except Exception as e:
            raise AssertionError(f"transcribe paralelo con stdout=None revento: {e!r}")
        elapsed = time.time() - t0
    finally:
        sys.stdout, sys.stderr = real_out, real_err

    assert not res.get("error"), res
    assert res.get("chunks") == 4, res
    assert res.get("workers", 1) > 1
    assert elapsed < dur * 5, f"100s de audio tardaron {elapsed:.0f}s (>5x duracion)"
    assert calls[-1] >= 0.99, f"el progreso no llego al 100% (ultimo {calls[-1]:.2f})"
    print(f"R1+R3 OK  100s headless (stdout=None) en {elapsed:.1f}s | "
          f"{res.get('workers')} workers | 100%={calls[-1]:.2f}")


if __name__ == "__main__":
    test_chunking()
    test_headless_single_chunk()
    test_headless_parallel()
    print("HEADLESS_ALL_OK")
