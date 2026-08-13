# -*- coding: utf-8 -*-
"""Prueba E2E del dialogo de microfono debil EJECUTANDO EL CODIGO EMPAQUETADO
del exe (dist_onefile/AudioClass.exe), no el fuente.

Fuerza un nivel bajo (p90 < umbral) y verifica en el codigo del exe:
 1. Se abre el dialogo con p90 + 'Mejor p90' (running max) y barra baja.
 2. Al llegar voz fuerte, la barra sube a verde y el 'Mejor p90' marca
    'Meta alcanzada'; el maximo NO baja si luego baja la voz.
 3. 'Continuar grabando' arranca la grabacion real (recording=True,
    'GRABANDO', boton Detener visible).
 4. Con nivel OK (p90 >= umbral) NO se abre dialogo: graba directo.

FALLA si cualquier asercion no se cumple. Requiere pantalla (se abre la app).
"""
import os
import sys
import json
import time
import types
import tempfile
import marshal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PyInstaller.archive.readers import CArchiveReader

ROOT = os.path.dirname(os.path.abspath(__file__))
# Por defecto valida el onefile; con AC_TEST_EXE=<ruta> se puede apuntar a
# otro exe (p. ej. el onedir dist/AudioClass/AudioClass.exe).
EXE = os.environ.get("AC_TEST_EXE") or os.path.join(ROOT, "dist_onefile", "AudioClass.exe")
c = CArchiveReader(EXE)
code = marshal.loads(c.extract("audioclass_v91"))

sys.modules["audioclass_v91"] = types.ModuleType("audioclass_v91")
mod = sys.modules["audioclass_v91"]
mod.__file__ = os.path.join(ROOT, "audioclass_v91.py")
mod.__package__ = ""
exec(code, mod.__dict__)
ac = mod

# Config aislada + salida a carpeta temporal (no tocar la real del usuario)
CFG = os.path.join(ROOT, "_micwarn_exe_config.json")
ac.CONFIG_PATH = CFG
cfg = ac.DEFAULT_CONFIG.copy()
cfg["first_run"] = False
cfg["theme"] = "dark"
with open(CFG, "w", encoding="utf-8") as f:
    json.dump(cfg, f)
ac.OUTPUT_DIR = tempfile.mkdtemp(prefix="ac_micwarn_exe_")

ac.App._fatal = lambda self, e: (_ for _ in ()).throw(RuntimeError(f"FATAL: {e}"))
ac.App._msg = lambda self, kind, title, msg: None
ac.App._ask = lambda self, t, m: True

failures = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


def pump(app, n=8, dt=0.12):
    for _ in range(n):
        time.sleep(dt)
        app.update()


def wait_until(app, cond, timeout=12.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if cond():
                return True
        except Exception:
            pass
        app.update()
        time.sleep(0.1)
    return False


def soft_stop(app):
    """Detiene la grabacion sin pasar por _procsave (la pipeline ya la cubren
    otros tests); solo cierra el stream y los hilos daemon."""
    app.recording = False
    try:
        app.stop_ev.set()
    except Exception:
        pass
    time.sleep(0.5)
    app.update()


# ═══ Instancia 1: ruta debil (p90 < umbral) ═══════════════════════════════
app = ac.App()
pump(app)

check("arranca sin grabar", not getattr(app, "recording", False))

# Fuerza nivel bajo como llegaria del pre-check (vía la cola real _poll)
app.q.put(("mic_probe", 0.003))
abrio = wait_until(app, lambda: getattr(app, "mic_warn_top", None) is not None
                   and app.mic_warn_top.winfo_exists())
check("nivel bajo abre el dialogo de advertencia", abrio)
check("aun no graba con dialogo abierto", not getattr(app, "recording", False))
check("status no dice GRABANDO", "GRABANDO" not in str(app.lstatus.cget("text")))

if getattr(app, "mic_warn_top", None) is not None:
    best_txt = app.mic_warn_best_lbl.cget("text")
    bar_val = app.mic_warn_bar.get() if hasattr(app.mic_warn_bar, "get") else 0.0
    check("muestra p90 medido", "0.003" in best_txt, best_txt)
    check("Mejor p90 arranca con meta sin alcanzar", "meta 0.03" in best_txt, best_txt)
    check("barra inicial baja", bar_val < 0.1, f"bar={bar_val:.3f}")

    # Detener el worker del medidor real (solo queda el que yo inyecto)
    app._mic_warn_decided = True
    time.sleep(0.3)
    app.update()

    # El usuario se acerca y habla: llega voz fuerte
    for _ in range(20):
        app.q.put(("mic_live", 0.05))
    pump(app, n=12, dt=0.1)
    check("Mejor p90 marca Meta alcanzada", "Meta alcanzada" in app.mic_warn_best_lbl.cget("text"),
          app.mic_warn_best_lbl.cget("text"))
    check("running max >= umbral verde", getattr(app, "mic_warn_best_p90", 0.0) >= 0.03,
          f"best={getattr(app, 'mic_warn_best_p90', 0.0):.4f}")
    check("barra en verde tras la voz",
          str(app.mic_warn_bar.cget("progress_color")).lower() == str(ac.C["ok"]).lower(),
          f"color={app.mic_warn_bar.cget('progress_color')}")
    # Mini-grafico de tendencia: debe haber barras dibujadas y el historial
    # de p90 por ventana debe reflejar la voz fuerte
    trend_items = len(app.mic_warn_trend.find_all())
    check("trend canvas dibuja barras + linea meta", trend_items > 0,
          f"items={trend_items}")
    # El primer valor es el p90 del pre-check (punto de partida, bajo); las
    # ventanas en vivo (desde el indice 1) deben reflejar la voz fuerte.
    hist = getattr(app, "mic_warn_p90_hist", [])
    check("trend historial refleja la voz (en vivo)",
          len(hist) > 1 and any(v >= 0.03 for v in hist)
          and all(v >= 0.03 for v in hist[1:]),
          str(hist))

    # La voz baja: el running max NO debe caer
    for _ in range(30):
        app.q.put(("mic_live", 0.001))
    pump(app, n=10, dt=0.1)
    check("maximo no baja aunque la voz baje", getattr(app, "mic_warn_best_p90", 0.0) >= 0.03,
          f"best={getattr(app, 'mic_warn_best_p90', 0.0):.4f}")
    check("label mantiene Meta alcanzada", "Meta alcanzada" in app.mic_warn_best_lbl.cget("text"))

    # Pulsar 'Continuar grabando' (mismo callback del boton)
    app._mic_warn_decide(True)
    pump(app)
    check("Continuar arranca la grabacion", getattr(app, "recording", False) is True)
    check("status GRABANDO", "GRABANDO" in str(app.lstatus.cget("text")),
          str(app.lstatus.cget("text")))
    check("boton Detener visible", bool(app.bstop.winfo_ismapped()))
    soft_stop(app)

app.destroy()
pump(app)

# ═══ Instancia 2: ruta OK (p90 >= umbral) — graba sin dialogo ══════════════
app2 = ac.App()
pump(app2)
app2.q.put(("mic_probe", 0.05))
ok = wait_until(app2, lambda: getattr(app2, "recording", False))
check("nivel OK graba directo (sin dialogo)", ok)
check("no abre dialogo con nivel OK",
      getattr(app2, "mic_warn_top", None) is None
      or not app2.mic_warn_top.winfo_exists())
soft_stop(app2)
app2.destroy()

print()
if failures:
    print(f"RESULTADO: MIC_WARN_ON_EXE FAIL ({len(failures)} fallos)")
    sys.exit(1)
print("RESULTADO: MIC_WARN_ON_EXE_OK")
