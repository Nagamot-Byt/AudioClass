"""test_transcribe_stub.py — Integracion del motor de transcripcion SIN el
modelo pesado (whisper/torch).

La transcripcion real de AudioClass requiere openai-whisper + torch + tiny.pt
(GBs de descarga). Para validar el CODIGO del motor de forma determinista en
CI/headless, este test inyecta stubs de 'whisper' y 'torch' en sys.modules y
ejercita LocalWhisperEngine.transcribe de punta a punta con audio REAL
(prueba_voz_es.wav repetida para forzar varios chunks de 30s):

  - chunking en ventanas de 30s con solapamiento
  - paralelismo real (ThreadPoolExecutor, un modelo deepcopy por worker)
  - callbacks de progreso con fraccion monotona y tiempo restante estimado
  - ensamblado de texto + segmentos y deteccion de alucinaciones

NO valida la calidad del modelo (eso lo hace test_e2e_transcripcion.py con el
modelo real), solo que la integracion del motor funciona.
"""

import copy
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from scipy.io import wavfile


# ── Stubs de torch y whisper (sin dependencias reales) ──────────────────────
class _FakeTorch:
    @staticmethod
    def get_num_threads():
        return 1

    @staticmethod
    def set_num_threads(n):
        return None


class _FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class _FakeModel:
    """Modelo whisper ficticio: devuelve texto estable y 1 segmento."""

    def transcribe(self, chunk, **kw):
        # openai-whisper devuelve dict con "segments" = lista de DICTs.
        # faster-whisper devuelve (segs, info) con segs = objetos.
        if kw.get("without_timestamps"):
            seg = _FakeSegment(0.0, 2.0, "texto simulado de transcripcion")
            return iter([seg]), type("Info", (), {"language": "es"})()
        return {
            "text": "texto simulado de transcripcion",
            "segments": [{"start": 0.0, "end": 2.0, "text": "texto simulado de transcripcion"}],
        }

    def detect_language(self, mel):
        return {"es": 0.99}


class _FakeWhisper:
    @staticmethod
    def load_model(*a, **k):
        return _FakeModel()

    @staticmethod
    def log_mel_spectrogram(audio):
        return audio


sys.modules.setdefault("torch", _FakeTorch())
sys.modules.setdefault("whisper", _FakeWhisper())


from audioclass_core import LocalWhisperEngine


def _savewav(path, arr):
    wavfile.write(path, 16000, np.int16(np.clip(arr, -1.0, 1.0) * 32767))


def main():
    base = HERE
    voice = os.path.join(base, "prueba_voz_es.wav")
    if not os.path.exists(voice):
        print("FATAL: falta prueba_voz_es.wav")
        return 1

    tmp = tempfile.gettempdir()
    wav_path = os.path.join(tmp, "ac_trans_stub.wav")
    sr, v = wavfile.read(voice)
    if v.dtype == np.int16:
        v = v.astype(np.float32) / 32768.0
    # Repetir ~5x para superar 30s y forzar varios chunks (paralelismo).
    raw = np.tile(v, 5)
    _savewav(wav_path, raw)
    print(f"[1] Audio simulado: {len(raw) / sr:.0f}s")

    eng = LocalWhisperEngine("tiny", backend="openai")
    eng.model = _FakeModel()
    eng.ready = True
    eng.model_name = "tiny"
    eng.language = "es"  # evita la rama de deteccion de idioma (auto)
    eng._resolve_model = lambda: wav_path
    eng._load_model_obj = staticmethod(lambda *a, **k: _FakeModel())

    msgs = []

    def cb(frac, total, msg):
        msgs.append((frac, total, msg))

    t0 = time.time()
    res = eng.transcribe(wav_path, timestamps=True, progress_callback=cb)
    elapsed = time.time() - t0
    txt = (res.get("text") or "").strip()
    print(f"[2] chunks={res.get('chunks')} workers={res.get('workers')} {elapsed:.1f}s")
    print(f"[3] text_len={len(txt)} segs={len(res.get('segments') or [])}")
    print(f"[4] cb_msgs={len(msgs)}")

    assert not res.get("error"), f"error inesperado: {res}"
    assert not res.get("cancelled"), "cancelado sin pedirlo"
    assert res.get("chunks", 0) >= 2, f"se esperaban >=2 chunks, got {res.get('chunks')}"
    assert res.get("workers", 0) > 1, f"se esperaba paralelismo, workers={res.get('workers')}"
    assert len(txt) > 0, "texto vacio"
    assert isinstance(res.get("segments"), list) and len(res["segments"]) > 0

    fracs = [f for f, _, _ in msgs]
    assert all(b >= a for a, b in zip(fracs, fracs[1:])), "progreso no monotono"
    assert any("rest" in m for _, _, m in msgs), "falta tiempo restante estimado"
    assert any("%" in m for _, _, m in msgs), "falta porcentaje en progreso"

    print("STUB_TRANSCRIBE_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
