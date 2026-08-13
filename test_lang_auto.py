#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_lang_auto.py — Modo de idioma 'auto' en LocalWhisperEngine.

Sustituye whisper por un modelo FALSO (sys.modules) para verificar SIN cargar
torch/whisper reales que:
  R1. language="es"   -> transcribe recibe language="es" y el prompt ES.
  R2. language="auto" -> se detecta el idioma (detect_language -> en) y todos
                         los chunks se transcriben con language="en" y el
                         prompt EN (consistencia entre chunks).
  R3. language="auto" -> deteccion que devuelve "es" -> language="es", prompt ES.
  R4. Camino PARALELO con auto (2+ chunks): todos los workers usan el mismo
      idioma detectado.
  R5. CloudColabEngine envia "language" en el form data.
  R6. El resultado de transcribe incluye "language".
"""
import os
import sys
import tempfile
import types

import numpy as np
from scipy.io import wavfile

# ── Fakes: NO cargan torch ni whisper reales ─────────────────────────────────
CALLS = []          # kwargs de cada llamada a transcribe (camino local)
DETECT_RESULT = {}  # lo que devuelve detect_language (se ajusta por test)
COLUB_FORM = {}     # form data capturado del CloudColabEngine


class FakeModel:
    def detect_language(self, mel):
        return dict(DETECT_RESULT)

    def transcribe(self, audio, **kwargs):
        CALLS.append(kwargs)
        lang = kwargs.get("language") or "es"
        text = "transcripcion de prueba" if lang == "es" else "test transcription"
        return {"text": text, "segments": [{"start": 0.0, "end": 1.0, "text": text}]}


def _install_fakes():
    wh = types.ModuleType("whisper")
    wh.load_model = lambda *a, **k: FakeModel()
    wh.log_mel_spectrogram = lambda audio: ("mel", audio)
    sys.modules["whisper"] = wh

    # torch: PROXY del real (scipy._external.array_api_compat accede a
    # torch.Tensor al importar; un fake minimo rompe el import de scipy).
    # Solo se sobrescriben las dos funciones que usa el camino paralelo del
    # motor, para que el test no pague el coste real de torch.
    try:
        import torch as _real_torch
    except ImportError:
        _real_torch = None
    t = types.ModuleType("torch")
    if _real_torch is not None:
        t.__dict__.update(_real_torch.__dict__)
    t.get_num_threads = lambda: 4
    t.set_num_threads = lambda n: None
    if not hasattr(t, "Tensor"):
        t.Tensor = float  # minimo para que scipy no reviente si no hay torch
    sys.modules["torch"] = t


def make_wav(duration_s):
    sr = 16000
    x = (np.random.randn(int(sr * duration_s)) * 0.01).astype(np.float32)
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    wavfile.write(path, sr, (x * 32767).astype(np.int16))
    return path


def test_es_forzado():
    import audioclass_core as core
    CALLS.clear()
    eng = core.LocalWhisperEngine("tiny", language="es", backend="openai")
    p = make_wav(8)   # 1 chunk -> camino secuencial
    try:
        r = eng.transcribe(p)
    finally:
        os.remove(p)
    assert r["language"] == "es", r.get("language")
    assert len(CALLS) == 1
    kw = CALLS[0]
    assert kw["language"] == "es"
    assert "español" in kw["initial_prompt"]
    print("  R1 OK: language='es' -> whisper language='es', prompt ES")


def test_auto_detecta_en():
    import audioclass_core as core
    CALLS.clear()
    DETECT_RESULT.update({"en": 0.92, "es": 0.05})
    eng = core.LocalWhisperEngine("tiny", language="auto", backend="openai")
    p = make_wav(8)
    try:
        r = eng.transcribe(p)
    finally:
        os.remove(p)
    assert r["language"] == "en", r.get("language")
    assert len(CALLS) == 1
    kw = CALLS[0]
    assert kw["language"] == "en"
    assert "university lecture" in kw["initial_prompt"]
    print("  R2 OK: auto detecto 'en' -> whisper language='en', prompt EN")


def test_auto_detecta_es():
    import audioclass_core as core
    CALLS.clear()
    DETECT_RESULT.update({"es": 0.9, "en": 0.08})
    eng = core.LocalWhisperEngine("tiny", language="auto", backend="openai")
    p = make_wav(8)
    try:
        r = eng.transcribe(p)
    finally:
        os.remove(p)
    assert r["language"] == "es", r.get("language")
    assert CALLS[0]["language"] == "es"
    assert "español" in CALLS[0]["initial_prompt"]
    print("  R3 OK: auto detecto 'es' -> whisper language='es', prompt ES")


def test_auto_paralelo_consistente():
    import audioclass_core as core
    CALLS.clear()
    DETECT_RESULT.update({"en": 0.95, "es": 0.03})
    eng = core.LocalWhisperEngine("tiny", language="auto", backend="openai")
    p = make_wav(70)   # 70s -> 3 chunks -> camino paralelo
    try:
        r = eng.transcribe(p)
    finally:
        os.remove(p)
    assert r["language"] == "en", r.get("language")
    assert r["workers"] > 1, r
    assert len(CALLS) == r["chunks"], (len(CALLS), r["chunks"])
    for kw in CALLS:
        assert kw["language"] == "en", kw
        assert "university lecture" in kw["initial_prompt"]
    print(f"  R4 OK: paralelo ({r['workers']} workers, {r['chunks']} chunks) "
          f"todos con language='en' y prompt EN")


def test_auto_tupla_whisper_real():
    """whisper 20250625 devuelve (tokens, {lang: prob}) y no un dict a secas:
    verifica que _resolve_lang acepta la tupla (bug encontrado en el log:
    AttributeError 'tuple' object has no attribute 'get' en modo auto)."""
    import audioclass_core as core
    CALLS.clear()

    class FakeTuplaModel:
        def detect_language(self, mel):
            return (["<|startoftranscript|>", "<|es|>"],
                    {"en": 0.05, "es": 0.93, "fr": 0.02})

        def transcribe(self, audio, **kwargs):
            CALLS.append(kwargs)
            lang = kwargs.get("language") or "es"
            return {"text": "texto es",
                    "segments": [{"start": 0.0, "end": 1.0, "text": "texto es"}]}

    eng = core.LocalWhisperEngine("tiny", language="auto", backend="openai")
    eng.model = FakeTuplaModel()
    p = make_wav(8)
    try:
        r = eng.transcribe(p)
    finally:
        os.remove(p)
    assert r["language"] == "es", r.get("language")
    assert CALLS[0]["language"] == "es"
    print("  R6 OK: detect_language en formato tupla (whisper real) -> 'es'")


def test_cloud_envia_language():
    import audioclass_core as core
    COLUB_FORM.clear()
    orig_post = None
    try:
        import requests
    except ImportError:
        print("  R5 SKIP: no hay requests")
        return
    import requests as _req

    class _Resp:
        status_code = 200
        def json(self):
            return {"text": "ok", "model": "large-v3", "device": "gpu"}

    def _fake_post(url, files=None, data=None, timeout=None):
        COLUB_FORM.update(data or {})
        return _Resp()

    orig_post = _req.post
    _req.post = _fake_post
    try:
        eng = core.CloudColabEngine("http://127.0.0.1:8000", "k", language="auto")
        p = make_wav(2)
        try:
            eng.transcribe(p)
        finally:
            os.remove(p)
    finally:
        _req.post = orig_post
    assert COLUB_FORM.get("language") == "auto", COLUB_FORM
    print("  R5 OK: CloudColabEngine envia language='auto' en el form")


def main():
    print("test_lang_auto.py — modo 'auto' de idioma en whisper")
    # Importar el nucleo ANTES de instalar los fakes: scipy debe ver su torch
    # (o ninguno) al importar, no el proxy.
    import audioclass_core  # noqa: F401
    _install_fakes()
    test_es_forzado()
    test_auto_detecta_en()
    test_auto_detecta_es()
    test_auto_paralelo_consistente()
    test_auto_tupla_whisper_real()
    test_cloud_envia_language()
    print("\nLANG_AUTO_ALL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
