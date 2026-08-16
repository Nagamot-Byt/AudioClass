# -*- coding: utf-8 -*-
"""Test de integracion del optimizador de microfono integrado en la app.

Sin microfono real ni CoreAudio: se inyecta un modulo optimizar_mic FAKE y un
sd.InputStream fake con audio sintetico. Valida:

- measure_signal(): devuelve las metricas correctas (piso/p90/peak/veredicto)
  para voz fuerte, silencio y error de stream, e invoca on_level por bloque.
- _mic_opt_worker(False): diagnostica (dispositivo, nivel, permiso, mics),
  corre la prueba de senal y termina con ("mic_opt_done", veredicto).
- _mic_opt_worker(True): aplica nivel 100% + boost, repite la prueba y
  compara antes/despues (xN en el resumen).
- El import del optimizador real funciona (Windows) — se toca la API real.

FALLA si cualquier rama no se comporta asi.
"""
import os
import sys
import queue
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

import audioclass_v91 as ac
import optimizar_mic as om

failures = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


class FakeStream:
    """Reemplaza sd.InputStream: entrega una vez el audio sintetico por bloque."""

    def __init__(self, samples, blocksize=800, fail=False, **kw):
        self.samples = samples
        self.bs = blocksize
        self.fail = fail
        self.cb = kw.get("callback")

    def __enter__(self):
        if self.fail:
            raise OSError("stream no disponible (test)")
        for i in range(0, len(self.samples), self.bs):
            blk = self.samples[i:i + self.bs]
            self.cb(blk.reshape(len(blk), 1), len(blk), None, None)
        return self

    def __exit__(self, *a):
        return False


def _fake_measure(level):
    """measure_signal fake: entrega bloques constantes y llama on_level."""
    def f(dur=4.0, on_level=None, device=None):
        SR = 16000
        n = int(dur * SR)
        x = np.full(n, level, np.float32)
        for i in range(0, n, 800):
            if on_level is not None:
                on_level(float(level))
        if level <= 1e-6:
            return {"dur": dur, "piso": 0.0, "p90": 0.0, "peak": 0.0, "veredicto": "SILENCIO"}
        return {"dur": dur, "piso": level, "p90": level, "peak": level, "veredicto": "OK"}
    return f


def _fake_om(levels):
    """Modulo optimizar_mic fake: niveles de señal por llamada (antes, despues)."""
    m = types.ModuleType("optimizar_mic")
    it = iter(levels)
    m._default_capture_device = lambda: "dev0"
    m._device_id = lambda d: "ID-DEFAULT"
    m.get_mic_state = lambda d: (100, False)
    m.privacy_mic = lambda: "Allow"
    m.list_mics = lambda: [("ID-DEFAULT", 100, False), ("ID-2", 80, True)]
    m.measure_signal = lambda dur=4.0, on_level=None, device=None: \
        _fake_measure(next(it))(dur, on_level, device)
    m.apply_mic_level = lambda dev, level: (True, "")
    m.apply_boost = lambda dev: (True, "boost +30 dB aplicado")
    m._capture_device_by_sd_name = lambda name: None
    m._device_friendly_name = lambda dev: None
    return m


def _run_worker(do_apply, levels):
    q = queue.Queue()
    stub = type("W", (), {"q": q, "pipeline": None})()
    orig = sys.modules.get("optimizar_mic")
    sys.modules["optimizar_mic"] = _fake_om(levels)
    try:
        ac.App._mic_opt_worker(stub, do_apply)
    finally:
        sys.modules["optimizar_mic"] = orig
    msgs = []
    while True:
        try:
            msgs.append(q.get_nowait())
        except queue.Empty:
            break
    return msgs


# ── measure_signal (API real, stream fake) ───────────────────────────────────
def _measure_with(level, fail=False):
    orig_stream, orig_sleep = om.sd.InputStream, om.sd.sleep
    om.sd.InputStream = lambda **kw: FakeStream(np.full(16000 * 2, level, np.float32), fail=fail, **kw)
    om.sd.sleep = lambda ms: None
    lvls = []
    try:
        r = om.measure_signal(2.0, on_level=lvls.append)
    finally:
        om.sd.InputStream, om.sd.sleep = orig_stream, orig_sleep
    return r, lvls

r, lvls = _measure_with(0.2)
check("measure_signal voz OK", r["veredicto"] == "OK" and r["p90"] > 0.15, str(r))
check("measure_signal on_level invocado", len(lvls) > 0, f"bloques={len(lvls)}")
check("measure_signal on_level valores", all(v > 0.15 for v in lvls))

r, _ = _measure_with(0.0)
check("measure_signal silencio", r["veredicto"] == "SILENCIO", str(r))

r, _ = _measure_with(0.2, fail=True)
check("measure_signal error stream", r["veredicto"].startswith("ERROR"), str(r))

# ── _mic_opt_worker: diagnostico ─────────────────────────────────────────────
msgs = _run_worker(False, [0.2])
text = "".join(d for mt, d in msgs if mt == "mic_opt_log")
check("diagnostico: dispositivo", "Dispositivo por defecto" in text)
check("diagnostico: nivel", "Nivel: 100%" in text)
check("diagnostico: permiso", "Permiso" in text and "Allow" in text)
check("diagnostico: mics", "ID-DEFAULT" in text and "ID-2" in text)
check("diagnostico: prueba", "p90" in text)
check("diagnostico: done OK", ("mic_opt_done", "OK") in msgs, f"done={[m for m in msgs if m[0]=='mic_opt_done']}")
check("diagnostico: aviso HABLA", any(mt == "mic_opt_state" and "HABLA" in d for mt, d in msgs))
check("diagnostico: no aplica boost", "boost del nodo" not in text)

# ── _mic_opt_worker: aplicar optimizacion ────────────────────────────────────
msgs = _run_worker(True, [0.01, 0.05])          # antes debil, despues OK
text = "".join(d for mt, d in msgs if mt == "mic_opt_log")
check("apply: nivel 100%", "nivel → 100%" in text)
check("apply: boost", "boost" in text)
check("apply: prueba antes y post", "Prueba:" in text and "Post:" in text)
check("apply: resumen xN", "x5.0" in text or "RESUMEN" in text, "RESUMEN" in text)
check("apply: done OK", ("mic_opt_done", "OK") in msgs)
check("apply: aviso post", any(mt == "mic_opt_state" and "post-optimización" in d for mt, d in msgs))

# ── Import del modulo REAL (Windows): funciones clave accesibles ─────────────
for fn in ("measure_signal", "test_signal", "apply_mic_level", "apply_boost",
           "get_mic_state", "privacy_mic", "list_mics"):
    check(f"optimizar_mic real expone {fn}", callable(getattr(om, fn, None)))

print()
if failures:
    print(f"RESULTADO: MIC_OPT_INTEGRATION FAIL ({len(failures)} fallos)")
    sys.exit(1)
print("RESULTADO: MIC_OPT_INTEGRATION_OK")
