# -*- coding: utf-8 -*-
"""test_watchdog.py — El watchdog por chunk impide el cuelgue infinito.

Replica el escenario del usuario (barra clavada en ~98% durante horas) de forma
DETERMINISTA: se inyectan modelos falsos cuyo transcribe() se queda dormido
para siempre. El motor debe:

  A) SECUENCIAL (30s -> 1 chunk) colgado: fallar con RuntimeError en segundos
     (cuando NINGUN chunk se transcribe es un fallo real, no un exito vacio).
  B) PARALELO (100s -> 4 chunks) todos colgados: igual, RuntimeError acotado.
  C) PARALELO PARCIAL: 1 de 4 chunks colgado y 3 OK -> devolver el texto de los
     chunks buenos con chunks_omitidos=1 (transcripcion parcial, sin abortar).

Nota: el camino secuencial solo aplica con 1 chunk (workers=min(nucleos,
chunks, RAM)); con >=2 chunks y multicore el motor va por el paralelo. Por eso
el caso "parcial" se prueba en paralelo.

Presupuesto mini: core.CHUNK_BUDGET_FLOOR=2, CHUNK_EST_SEED=0.5 -> 2s por chunk.
"""
import itertools
import os, sys, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from scipy.io import wavfile
import audioclass_core as core

core.CHUNK_BUDGET_FLOOR = 2.0
core.CHUNK_EST_SEED = 0.5

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(BASE, "models", "tiny.pt")


class _HungModel:
    """Modelo falso: whisper que nunca responde (simula el bucle de timestamps)."""

    def transcribe(self, *a, **k):
        time.sleep(999)


class _HangOneModel:
    """Solo el primer worker que empiece se cuelga; el resto devuelve texto.
    El contador es DE CLASE (sobrevive al deepcopy por worker del motor) y
    usa itertools.count: su next() es atomico en C, sin carreras entre los
    workers concurrentes."""

    _seq = itertools.count(1)

    def transcribe(self, *a, **k):
        if next(type(self)._seq) == 1:
            time.sleep(999)
        return {"text": "clase de prueba", "segments": []}


def _wav(dur):
    p = os.path.join(tempfile.gettempdir(), f"ac_watchdog_{dur}s.wav")
    wavfile.write(p, core.SAMPLE_RATE, np.int16(np.zeros(int(core.SAMPLE_RATE * dur), np.int16)))
    return p


def _engine():
    # backend="openai": este test inyecta modelos falsos vía _model_template
    # (deepcopy) y valida el camino del EXE compilado. El camino faster se
    # valida en test_mejoras_v10.py.
    eng = core.LocalWhisperEngine("tiny", backend="openai")
    eng._resolve_model = lambda: MODEL
    return eng


def test_sequential_all_hang():
    eng = _engine()
    eng.model = _HungModel()   # camino secuencial usa self.model directamente
    t0 = time.time()
    try:
        # check_silence=False: los WAVs de prueba son puros ceros (silencio
        # digital) y la pre-validacion los rechazaria antes de probar el
        # watchdog de timeouts.
        eng.transcribe(_wav(30), timestamps=False, progress_callback=lambda *a: None,
                       check_silence=False)
        raise AssertionError("deberia haber fallado con RuntimeError (todo colgado)")
    except RuntimeError as e:
        assert "omitidos por timeout" in str(e), e
    el = time.time() - t0
    assert el < 30, f"el watchdog no corto el cuelgue secuencial ({el:.1f}s)"
    assert eng.model is None, "tras un timeout el modelo debe invalidarse"
    print(f"WD-A OK  secuencial todo colgado -> RuntimeError en {el:.1f}s")


def test_parallel_all_hang():
    eng = _engine()
    eng._model_template = {MODEL: _HungModel()}   # deepcopy por worker -> todos cuelgan
    t0 = time.time()
    try:
        eng.transcribe(_wav(100), timestamps=False, progress_callback=lambda *a: None,
                       check_silence=False)
        raise AssertionError("deberia haber fallado con RuntimeError (todo colgado)")
    except RuntimeError as e:
        assert "chunks" in str(e), e
    el = time.time() - t0
    assert el < 30, f"el watchdog no corto el cuelgue paralelo ({el:.1f}s)"
    print(f"WD-B OK  paralelo todo colgado -> RuntimeError en {el:.1f}s")


def test_parallel_partial():
    eng = _engine()
    _HangOneModel._seq = itertools.count(1)
    eng._model_template = {MODEL: _HangOneModel()}
    t0 = time.time()
    res = eng.transcribe(_wav(100), timestamps=False, progress_callback=lambda *a: None,
                         check_silence=False)
    el = time.time() - t0
    assert el < 30, f"parcial tardo {el:.1f}s"
    assert res.get("chunks") == 4, res
    assert res.get("chunks_omitidos") == 1, res
    assert "clase de prueba" in (res.get("text") or ""), res
    print(f"WD-C OK  parcial paralelo (1 colgado + 3 OK) en {el:.1f}s | omitidos=1 | texto presente")


if __name__ == "__main__":
    test_sequential_all_hang()
    test_parallel_all_hang()
    test_parallel_partial()
    print("WATCHDOG_ALL_OK")
    sys.stdout.flush()
    # Los hilos que simulan el cuelgue siguen dormidos (999s): sin os._exit el
    # proceso no termina. Todo lo verificable ya se verifico arriba.
    os._exit(0)
