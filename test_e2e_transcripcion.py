# -*- coding: utf-8 -*-
"""Prueba E2E del flujo real de AudioClass: grabar → pipeline → transcribir.

Replica EXACTAMENTE lo que hace la app (ver App._procsave en audioclass_v91.py):
  1. El audio capturado se concatena y se guarda como WAV int16 (crudo).
  2. AudioPipeline.process lo procesa (perfil Clase Universitaria, VAD on).
  3. El procesado se guarda como WAV int16 (mejorado) y esa ruta es self.last_path.
  4. LocalWhisperEngine.transcribe transcribe ese WAV con el motor PARALELO
     (ThreadPoolExecutor, un modelo deepcopy por worker).

La "grabación" se simula con voz REAL (prueba_voz_es.wav) repetida ~5x para
superar 30s y forzar varios chunks de 30s (paralelismo real).

Valida:
- El texto generado supera un umbral (len > 100) → la transcripción sale.
- Hay mensajes de progreso con tiempo restante estimado ("rest").
- workers > 1 (paralelismo real) cuando hay >= 2 chunks.
- El progreso es monótono (la barra nunca retrocede).
- El pipeline no destruye la señal (el procesado conserva energía/duración útil).
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


def _savewav(path, arr):
    """Mismo formato que App._savewav: int16 PCM a 16 kHz mono."""
    wavfile.write(path, ac.SAMPLE_RATE, np.int16(np.clip(arr, -1.0, 1.0) * 32767))


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    voice = os.path.join(base, "prueba_voz_es.wav")
    if not os.path.exists(voice):
        print("FATAL: falta prueba_voz_es.wav (audio de voz real para el test)")
        return 1

    tmp = tempfile.gettempdir()
    raw_path = os.path.join(tmp, "ac_e2e_raw.wav")
    proc_path = os.path.join(tmp, "ac_e2e_mejorado.wav")

    # ── 1. Simular la grabación: voz real repetida ~5x (~104s -> 4 chunks) ──
    sr, v = wavfile.read(voice)
    if v.dtype == np.int16:
        v = v.astype(np.float32) / 32768.0
    raw = np.tile(v, 5)
    _savewav(raw_path, raw)
    print(f"[1/4] 'Grabación' simulada: voz real x5 = {len(raw)/sr:.0f}s")

    # ── 2. Pipeline profesional (igual que App._procsave) ──────────────────
    pipe = ac.AudioPipeline("Clase Universitaria", fast_mode=False, use_vad=True)
    steps = []
    t0 = time.time()
    proc = pipe.process(raw, progress_callback=lambda s, t, n: steps.append(n))
    t_pipe = time.time() - t0
    print(f"[2/4] Pipeline: {t_pipe:.1f}s · {len(steps)} etapas · salida {len(proc)/sr:.1f}s")
    # El procesado no debe quedar vacío ni perder toda la señal
    assert len(proc) > 0, "El pipeline devolvió audio vacío"
    rms = float(np.sqrt(np.mean(proc ** 2))) if len(proc) else 0.0
    assert rms > 0.01, f"El pipeline casi silenció el audio (rms={rms:.4f})"

    # ── 3. Guardar procesado (int16) y transcribir con el motor paralelo ───
    _savewav(proc_path, proc)
    print("[3/4] Procesado guardado (int16)")

    import whisper
    eng = ac.LocalWhisperEngine("tiny", backend="openai")
    eng.model = whisper.load_model(os.path.join(base, "models", "tiny.pt"))
    eng.ready = True
    eng.model_name = "tiny"
    eng._resolve_model = lambda: os.path.join(base, "models", "tiny.pt")

    msgs = []
    t0 = time.time()
    res = eng.transcribe(proc_path, timestamps=False,
                         progress_callback=lambda f, t, m: msgs.append((f, m)))
    elapsed = time.time() - t0
    txt = (res.get("text") or "").strip()
    print(f"[4/4] Transcripción: {res.get('workers')} workers · "
          f"{res.get('chunks')} chunks · {elapsed:.1f}s")

    # ── Validaciones ───────────────────────────────────────────────────────
    print("TEXT_LEN:", len(txt))
    print("TEXT_START:", repr(txt[:160]))
    print("WORKERS:", res.get("workers"), "CHUNKS:", res.get("chunks"))
    print("CB_MSGS:", len(msgs))

    assert not res.get("error"), res
    assert not res.get("cancelled"), res
    assert len(txt) > 100, f"Transcripción vacía o demasiado corta ({len(txt)} chars)"

    est = [m for _, m in msgs if "rest" in m]
    print("MSGS_CON_TIEMPO_RESTANTE:", len(est))
    for m in est[:3]:
        print("   ", m)
    assert len(est) > 0, "No apareció ningún mensaje con tiempo restante estimado"
    assert any("%" in m for _, m in msgs), "No apareció porcentaje en el progreso"

    chunks = res.get("chunks") or 0
    workers = res.get("workers") or 1
    if chunks >= 2:
        assert workers > 1, f"Se esperaba paralelismo real, workers={workers}"

    fracs = [f for f, _ in msgs]
    assert all(b >= a for a, b in zip(fracs, fracs[1:])), "El progreso retrocedió"
    print("MONOTONIC: True")

    print("E2E_TRANS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
