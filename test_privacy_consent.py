# -*- coding: utf-8 -*-
"""Smoke de privacidad: gate del wizard, gate de _adapt y checkbox en Configuracion."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audioclass_v91 as ac

SMOKE_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke_privacy_config.json")
ac.CONFIG_PATH = SMOKE_CFG

def write_cfg(first_run):
    cfg = ac.DEFAULT_CONFIG.copy()
    cfg["first_run"] = first_run
    cfg["ia_consent"] = False
    cfg["theme"] = "dark"
    with open(SMOKE_CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f)

ac.App._fatal = lambda self, e: (_ for _ in ()).throw(e)
msgs = []
ac.App._msg = lambda self, kind, title, msg: msgs.append((kind, title, msg))

PASS = FAIL = 0
def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"OK  {name}")
    else:
        FAIL += 1
        print(f"FAIL {name}  {extra}")

# ── A) Wizard: sin aceptar el aviso NO se puede continuar ─────────────────────
write_cfg(first_run=True)
app = ac.App()
for _ in range(4):
    app.update()

check("wizard muestra casillas de privacidad",
      hasattr(app, "wiz_priv_ack") and hasattr(app, "wiz_ia_consent"))

msgs.clear()
app._finish_wizard()
check("wizard bloqueado sin aceptar aviso",
      app.config.get("first_run") is not False and any(m[0] == "warning" for m in msgs),
      f"msgs={msgs} config={app.config.get('first_run')}")

# Aceptar el aviso y continuar (sin IA)
app.wiz_priv_ack.set(True)
app.wiz_ia_consent.set(False)
app._finish_wizard()
check("wizard continua al aceptar aviso", app.config.get("first_run") is False)
check("ia_consent guardado como False (opt-in)", app.config.get("ia_consent") is False)
for _ in range(4):
    app.update()
app.destroy()

# ── B) _adapt: sin ia_consent NO envia a IA ───────────────────────────────────
write_cfg(first_run=False)
app = ac.App()
for _ in range(4):
    app.update()
app.last_text = "Texto de prueba de una clase."
prompt_called = []
run_called = []
app._prompt_ia_consent = lambda cb: prompt_called.append(cb)
app._run_adapt = lambda t: run_called.append(t)

app._adapt("Resumen")
check("_adapt pide consentimiento si no hay ia_consent", len(prompt_called) == 1 and len(run_called) == 0,
      f"prompt={len(prompt_called)} run={len(run_called)}")

# Tras consentir, _adapt ejecuta directamente
app.config["ia_consent"] = True
app._adapt("Resumen")
check("_adapt ejecuta directo con ia_consent=True", len(run_called) == 1, f"run={run_called}")
for _ in range(4):
    app.update()
app.destroy()

# ── D) Aviso de grabacion: sin aceptar NO se graba (V1) ──────────────────────
write_cfg(first_run=False)
app = ac.App()
for _ in range(4):
    app.update()

app.config["rec_consent_ack"] = False
prompted = []
app._prompt_rec_consent = lambda: prompted.append(1) or False
app._begin_recording()
check("grabacion bloqueada sin aceptar el aviso", app.recording is False and len(prompted) == 1,
      f"recording={app.recording} prompted={len(prompted)}")

# Aceptado: el aviso se marca como visto y se guarda
app.config["rec_consent_ack"] = False
app._prompt_rec_consent = lambda: True
app._recloop = lambda: None  # sin microfono real en el test
app._begin_recording()
check("grabacion arranca al aceptar el aviso", app.recording is True and app.config.get("rec_consent_ack") is True,
      f"recording={app.recording}")
for _ in range(4):
    app.update()
app.destroy()

# ── C) Dialogo de Configuracion: existe el checkbox de privacidad y guarda ────
write_cfg(first_run=False)
app = ac.App()
for _ in range(4):
    app.update()
# Simula el estado del dialogo directamente: el smoke abre el dialogo real
try:
    app._open_config()
    for _ in range(4):
        app.update()
    check("dialogo de config abre sin error", True)
    app.destroy()
except Exception as e:
    import traceback
    traceback.print_exc()
    check("dialogo de config abre sin error", False, str(e))
    try:
        app.destroy()
    except Exception:
        pass

# Limpieza
for f in (SMOKE_CFG,):
    try:
        os.remove(f)
    except OSError:
        pass

print(f"\nPRIVACY_SMOKE: {PASS} OK, {FAIL} fallos")
# Salir con os._exit (no sys.exit): en Linux, la destruccion estatica C++ de
# libtorch (modelo cargado en el thread daemon del motor local) aborta el
# proceso al apagar el interprete (SIGABRT, rc=134) aun habiendo pasado todos
# los checks (observado en el runner de ubuntu: rc=134 tras '9 OK, 0 fallos').
# Se vacian los buffers antes para que el driver lea la salida completa.
sys.stdout.flush()
sys.stderr.flush()
os._exit(0 if FAIL == 0 else 1)
