# -*- coding: utf-8 -*-
"""Test de la advertencia visible de microfono debil (pre-check antes de grabar).

Valida la logica de _mic_probe_done, el dialogo de advertencia con p90 +
medidor en vivo, la decision Continuar/Cancelar y el worker del medidor, SIN
microfono real (stubs / audio sintetico):

- Nivel debil      -> abre el dialogo (_open_mic_warn_dialog) y NO graba aun.
- Nivel OK o None  -> graba directo, sin dialogo (nunca bloquear).
- _mic_warn_decide(True)  -> cierra el dialogo y arranca la grabacion.
- _mic_warn_decide(False) -> cierra el dialogo, restaura la UI, no graba.
- _mic_live_probe_worker  -> envia (\"mic_live\", rms) por la cola.

FALLA si alguna rama no se comporta asi. Correrlo junto a la suite de UI.
"""
import os
import sys
import queue

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

import audioclass_v91 as ac

failures = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


class _Lbl:
    def configure(self, text=None, text_color=None):
        self.text = text


class FakeTop:
    def __init__(self):
        self.destroyed = False

    def winfo_exists(self):
        return not self.destroyed

    def destroy(self):
        self.destroyed = True


class StubApp:
    """Mini-app con solo lo que usan _mic_probe_done / _mic_warn_decide."""

    def __init__(self):
        self._mic_probe_pending = True
        self.opened_warn = 0
        self.began = 0
        self.opened_opt = 0
        self.opt_started = 0
        self.opt_apply = None
        self.lstatus = _Lbl()
        self.mic_warn_top = None

    def _open_mic_warn_dialog(self, level):
        self.opened_warn += 1
        self.last_level = level

    def _begin_recording(self):
        self.began += 1

    def _open_mic_opt(self):
        self.opened_opt += 1

    def _mic_opt_start(self, do_apply):
        self.opt_started += 1
        self.opt_apply = do_apply


class FakeStream:
    """Reemplaza sd.InputStream: entrega una vez el audio sintetico."""

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


# ── _mic_probe_done: decide si abre dialogo o graba directo ──────────────────
s = StubApp()
ac.App._mic_probe_done(s, 0.003)
check("debil abre dialogo (no graba aun)", s.opened_warn == 1 and s.began == 0,
      f"warn={s.opened_warn} began={s.began}")
check("debil resetea pending", s._mic_probe_pending is False)
check("debil pasa el nivel medido", getattr(s, "last_level", None) == 0.003)

s = StubApp()
ac.App._mic_probe_done(s, 0.05)
check("nivel OK graba sin dialogo", s.began == 1 and s.opened_warn == 0)

s = StubApp()
ac.App._mic_probe_done(s, None)
check("probe None graba sin dialogo", s.began == 1 and s.opened_warn == 0)

s = StubApp()
ac.App._mic_probe_done(s, ac.MIC_PROBE_P90_MIN)
check("borde==umbral graba sin dialogo", s.began == 1 and s.opened_warn == 0)

# ── _mic_warn_decide: Continuar / Cancelar ───────────────────────────────────
s = StubApp()
s.mic_warn_top = FakeTop()
top_ref = s.mic_warn_top
s._mic_warn_decided = False
ac.App._mic_warn_decide(s, True)
check("decide continuar graba", s.began == 1, f"began={s.began}")
check("decide continuar cierra dialogo", top_ref.destroyed)
check("decide continuar marca flag", s._mic_warn_decided is True)
check("decide continuar limpia ref", s.mic_warn_top is None)

s = StubApp()
s.mic_warn_top = FakeTop()
top_ref = s.mic_warn_top
s._mic_warn_decided = False
ac.App._mic_warn_decide(s, False)
check("decide cancelar no graba", s.began == 0)
check("decide cancelar restaura UI", getattr(s.lstatus, "text", None) == "Listo")
check("decide cancelar cierra dialogo", top_ref.destroyed)

s = StubApp()                                     # sin dialogo abierto
ac.App._mic_warn_decide(s, False)
check("decide sin dialogo no rompe", s.began == 0 and getattr(s.lstatus, "text", None) == "Listo")

# ── _mic_warn_open_opt: abrir optimizador sin cancelar ───────────────────────
s = StubApp()
s.mic_warn_top = FakeTop()
top_ref = s.mic_warn_top
s._mic_warn_decided = False
ac.App._mic_warn_open_opt(s)
check("open_opt cierra advertencia", top_ref.destroyed and s.mic_warn_top is None)
check("open_opt marca flag (detiene medidor)", s._mic_warn_decided is True)
check("open_opt abre el optimizador", s.opened_opt == 1, f"opt={s.opened_opt}")
check("open_opt lanza Aplicar optimizacion", s.opt_started == 1 and s.opt_apply is True,
      f"started={s.opt_started} apply={s.opt_apply}")
check("open_opt no graba aun", s.began == 0)
check("open_opt restaura UI", getattr(s.lstatus, "text", None) == "Listo")

# ── _mic_live_probe_worker: medidor en vivo por la cola ──────────────────────
def _run_live(level, fail=False):
    q = queue.Queue()
    stub = type("W", (), {"q": q})()
    stub._mic_warn_decided = True                  # salir del loop de inmediato
    orig_stream, orig_sleep = ac.sd.InputStream, ac.time.sleep
    ac.sd.InputStream = lambda **kw: FakeStream(
        np.full(int(0.1 * ac.SAMPLE_RATE), level, np.float32), fail=fail, **kw)
    ac.time.sleep = lambda *a: None
    try:
        ac.App._mic_live_probe_worker(stub)
    finally:
        ac.sd.InputStream, ac.time.sleep = orig_stream, orig_sleep
    msgs = []
    while True:
        try:
            msgs.append(q.get_nowait())
        except queue.Empty:
            break
    return msgs

msgs = _run_live(0.05)
check("live worker envia nivel alto", any(mt == "mic_live" and r > 0.04 for mt, r in msgs),
      str(msgs[:2]))
msgs = _run_live(0.001)
check("live worker envia nivel bajo", any(mt == "mic_live" and r < 0.002 for mt, r in msgs),
      str(msgs[:2]))
msgs = _run_live(0.05, fail=True)
check("live worker con stream roto no lanza", msgs == [], str(msgs[:2]))

# ── _update_mic_warn_best: running max del p90 en vivo ───────────────────────
class _Lbl2:
    def __init__(self):
        self.exists = True
        self.text = None
        self.tc = None

    def winfo_exists(self):
        return self.exists

    def configure(self, text=None, text_color=None):
        self.text = text
        self.tc = text_color


class TrendStub:
    """Stub con _draw_mic_warn_trend (lo llama _update_mic_warn_best); sin
    canvas no dibuja nada pero no rompe."""
    _draw_mic_warn_trend = ac.App._draw_mic_warn_trend


s = TrendStub()
s.mic_warn_best_p90 = 0.005
s.mic_warn_best_lbl = _Lbl2()
for _ in range(20):
    ac.App._update_mic_warn_best(s, 0.05)
check("best sube a verde tras hablar", s.mic_warn_best_p90 >= 0.03
      and "Meta alcanzada" in s.mic_warn_best_lbl.text, f"best={s.mic_warn_best_p90}")
for _ in range(30):                       # la voz baja: el max NO debe caer
    ac.App._update_mic_warn_best(s, 0.001)
check("best no baja aunque la voz baje", s.mic_warn_best_p90 >= 0.03,
      f"best={s.mic_warn_best_p90}")
check("best label mantiene meta alcanzada", "Meta alcanzada" in s.mic_warn_best_lbl.text)

s2 = TrendStub()
s2.mic_warn_best_p90 = 0.004
s2.mic_warn_best_lbl = _Lbl2()
for _ in range(10):
    ac.App._update_mic_warn_best(s2, 0.004)
check("best inicial debil = warn con meta", s2.mic_warn_best_p90 < 0.03
      and "meta 0.03" in s2.mic_warn_best_lbl.text, f"best={s2.mic_warn_best_p90}")

# ── Tendencia del p90 (mini-grafico): ventanas de 0.5 s, max 20 barras ──────
s3 = TrendStub()
for _ in range(12):                              # 12 lecturas -> 2 ventanas
    ac.App._update_mic_warn_best(s3, 0.05)
check("trend acumula ventanas p90", len(getattr(s3, "mic_warn_p90_hist", [])) >= 2,
      str(len(getattr(s3, "mic_warn_p90_hist", []))))
check("trend valores reflejan la senal", all(v >= 0.03 for v in s3.mic_warn_p90_hist),
      str(s3.mic_warn_p90_hist))
for _ in range(200):                             # muchas mas -> cap a 20 barras
    ac.App._update_mic_warn_best(s3, 0.05)
check("trend limitado a 20 ventanas (~10 s)", len(s3.mic_warn_p90_hist) <= 20,
      str(len(s3.mic_warn_p90_hist)))

# sin canvas (stub) no rompe al dibujar
ac.App._draw_mic_warn_trend(s3)
check("draw trend sin canvas no rompe", True)

# ── _mic_probe_worker: calculo del p90 del pre-check (1.5 s) ─────────────────
class FakePipeline:
    """pipeline stub: un solo frame con el RMS global del audio."""

    def _frame_rms(self, audio, window, hop):
        return np.array([float(np.sqrt(np.mean(audio ** 2)))])


def _run_probe(level, fail=False):
    q = queue.Queue()
    stub = type("W", (), {"q": q, "pipeline": FakePipeline()})()
    orig_stream, orig_sleep = ac.sd.InputStream, ac.time.sleep
    ac.sd.InputStream = lambda **kw: FakeStream(
        np.full(int(0.1 * ac.SAMPLE_RATE), level, np.float32), fail=fail, **kw)
    ac.time.sleep = lambda *a: None
    try:
        ac.App._mic_probe_worker(stub)
    finally:
        ac.sd.InputStream, ac.time.sleep = orig_stream, orig_sleep
    return q.get_nowait()


mt, lvl = _run_probe(0.1)
check("probe worker envia nivel alto", mt == "mic_probe" and lvl is not None and lvl >= 0.09,
      f"mt={mt} lvl={lvl}")
mt, lvl = _run_probe(1e-9)
check("probe worker envia nivel ~silencio", mt == "mic_probe" and lvl is not None and lvl < ac.MIC_PROBE_P90_MIN,
      f"mt={mt} lvl={lvl}")
mt, lvl = _run_probe(0.1, fail=True)
check("probe worker falla -> None (no bloquea)", mt == "mic_probe" and lvl is None, f"mt={mt} lvl={lvl}")

print()
if failures:
    print(f"RESULTADO: MIC_PROBE_WARN FAIL ({len(failures)} fallos)")
    sys.exit(1)
print("RESULTADO: MIC_PROBE_WARN_OK")
