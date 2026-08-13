"""test_stability.py — Criterios avanzados de estabilidad.

A) Tope GLOBAL de la cache de modelos (LRU por ruta): cambiar de modelo
   (tiny/base/small) no acumula RAM indefinidamente (antes: 8 copias POR ruta).
B) Round-trip _cache_get/_cache_put (pop correcto, cache vacia tras consumir).
C) Churn: muchas put/get no crecen la cache por encima del presupuesto.
D) Higiene de hilos: tras una transcripcion real, threading.active_count()
   vuelve a la linea base (workers del pool + reporter se limpian).
E) Barrido de temporales: _sweep_stale_temps borra .raw viejos y respeta los
   recientes (no borra una grabacion en curso).
"""
import os
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.getcwd())
import numpy as np

from audioclass_core import LocalWhisperEngine, _MODEL_CACHE_MAX
import audioclass_v91 as ac  # _sweep_stale_temps

BASE = threading.active_count()


def test_cache_cap():
    eng = LocalWhisperEngine("tiny")
    # 3 rutas x 8 puts = 24 objetos; el presupuesto global es _MODEL_CACHE_MAX
    for i in range(3):
        for _ in range(8):
            eng._cache_put(f"ruta{i}", object())
    total = sum(len(v) for v in eng._model_cache.values())
    assert total <= _MODEL_CACHE_MAX, f"cache sin tope: {total} > {_MODEL_CACHE_MAX}"
    sizes = [len(eng._model_cache.get(f"ruta{i}", [])) for i in range(3)]
    # LRU: la ruta mas reciente retiene mas que la mas antigua
    assert sizes[2] >= sizes[0], f"LRU invertido: {sizes}"
    print(f"A OK  total={total} (tope {_MODEL_CACHE_MAX}) reparto={sizes}")


def test_roundtrip():
    eng = LocalWhisperEngine("tiny")
    o = object()
    eng._cache_put("x", o)
    got = eng._cache_get("x")
    assert got is o, "round-trip fallo"
    assert eng._cache_get("x") is None, "cache vacia tras pop"
    print("B OK  round-trip y pop")


def test_churn():
    eng = LocalWhisperEngine("tiny")
    for i in range(200):
        eng._cache_put("p", object())
        if i % 3 == 0:
            eng._cache_get("p")
    total = sum(len(v) for v in eng._model_cache.values())
    assert total <= _MODEL_CACHE_MAX, f"churn crecio: {total}"
    print(f"C OK  churn 200 ops -> cache estable en {total}")


def test_thread_hygiene():
    from scipy.io import wavfile
    sr, v = wavfile.read("prueba_voz_es.wav")
    if v.dtype == np.int16:
        v = v.astype(np.float32) / 32768.0
    tmp = os.path.join(tempfile.gettempdir(), "ac_stab.wav")
    wavfile.write(tmp, sr, np.int16(np.clip(v, -1, 1) * 32767))
    eng = LocalWhisperEngine("tiny", backend="openai")
    eng._resolve_model = lambda: os.path.join(os.getcwd(), "models", "tiny.pt")
    res = eng.transcribe(tmp, False)
    assert not res.get("cancelled"), "no debio cancelarse"
    assert res.get("text"), "sin texto"
    time.sleep(1.0)  # margen para que los daemon terminen de salir
    delta = threading.active_count() - BASE
    assert delta <= 3, f"fuga de hilos: {delta}"
    print(f"D OK  hilos delta={delta} | texto={res['text'][:40]!r}")
    os.remove(tmp)


def test_sweep():
    tdir = tempfile.gettempdir()
    old = os.path.join(tdir, "ac_rec_stale.raw")
    new = os.path.join(tdir, "ac_rec_fresh.raw")
    with open(old, "wb") as f:
        f.write(b"\0" * 16)
    with open(new, "wb") as f:
        f.write(b"\0" * 16)
    t_old = time.time() - 7200
    os.utime(old, (t_old, t_old))  # 2h -> obsoleto
    ac._sweep_stale_temps(max_age=3600)
    assert not os.path.exists(old), "no borro el .raw viejo"
    assert os.path.exists(new), "borro el .raw reciente"
    os.remove(new)
    print("E OK  barrido: viejo borrado, reciente intacto")


if __name__ == "__main__":
    test_cache_cap()
    test_roundtrip()
    test_churn()
    test_thread_hygiene()
    test_sweep()
    print("\nSTABILITY_ALL_OK")
