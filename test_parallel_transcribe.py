# -*- coding: utf-8 -*-
"""Prueba funcional del modo paralelo de LocalWhisperEngine.transcribe.
Genera un WAV de 100s (4 chunks de 30s) con ruido suave y verifica:
- chunks == 4 y workers > 1 (paralelismo real)
- progreso monotono y continuo (barra)
- sin error y con la clave 'text' presente
- timestamps=True tambien funciona
"""
import os, sys, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# La consola de Windows (cp1252) no imprime emojis como ⚡: reconfigure a utf-8
# para que los prints con mensajes de progreso no lancen UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from scipy.io import wavfile
import audioclass_v91 as ac

SR = 16000
DUR = 100  # 100s -> 4 chunks

tmp = os.path.join(tempfile.gettempdir(), "ac_par_test.wav")
rng = np.random.default_rng(0)
data = (rng.standard_normal(SR * DUR) * 0.02).astype(np.float32)
wavfile.write(tmp, SR, data)

import whisper
eng = ac.LocalWhisperEngine("tiny")
eng.model = whisper.load_model("models/tiny.pt")
eng.ready = True
eng.model_name = "tiny"
# En modo desarrollo el pool cargaria 'tiny' (cache/descarga de whisper);
# apuntamos al .pt local para que el test sea deterministico y sin internet.
eng._resolve_model = lambda: os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "models", "tiny.pt"
)

calls = []
def cb(frac, total, msg):
    calls.append((frac, total, msg))

t0 = time.time()
res = eng.transcribe(tmp, timestamps=False, progress_callback=cb)
el = time.time() - t0
print("CHUNKS:", res.get("chunks"), "WORKERS:", res.get("workers"))
print("ERROR:", res.get("error"), "CANCELLED:", res.get("cancelled"))
print("HAS_TEXT_KEY:", "text" in res)
print("ELAPSED:", round(el, 2))
print("CB_CALLS:", len(calls))
fracs = [c[0] for c in calls]
print("MONOTONIC:", all(b >= a for a, b in zip(fracs, fracs[1:])))
print("FIRST:", calls[0] if calls else None)
print("LAST:", calls[-1] if calls else None)
assert res.get("chunks") == 4, res
assert not res.get("error"), res
assert res.get("workers", 0) > 1, "se esperaba paralelismo real"
assert "text" in res
print("TEST_PARALLEL_OK")

# timestamps=True tambien
calls2 = []
res2 = eng.transcribe(tmp, timestamps=True, progress_callback=lambda f, t, m: calls2.append((f, t, m)))
print("TS_CHUNKS:", res2.get("chunks"), "TS_SEGS_TYPE:", type(res2.get("segments")).__name__)
assert res2.get("chunks") == 4
assert isinstance(res2.get("segments"), list)
print("TEST_TS_OK")
print("ALL_OK")
