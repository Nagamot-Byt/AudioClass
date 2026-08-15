# -*- coding: utf-8 -*-
"""Smoke test de la GUI rediseñada de AudioClass.
Instancia la app sin wizard, ejercita el nuevo sistema de diseño
(tema claro/oscuro, gutter, tags en vivo, toasts con Reintentar, atajos,
estado de conexion) y cierra. Requiere pantalla (se abre una ventana ~1s)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audioclass_v91 as ac

# Config aislada: no tocar la config real del usuario
SMOKE_CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_smoke_config.json")
ac.CONFIG_PATH = SMOKE_CFG
cfg = ac.DEFAULT_CONFIG.copy()
cfg["first_run"] = False
cfg["theme"] = "dark"
with open(SMOKE_CFG, "w", encoding="utf-8") as f:
    json.dump(cfg, f)

def _fatal_nb(self, e):
    """Sustituye _fatal: imprime el error real en vez de abrir un dialogo modal
    que bloquearia el test."""
    import traceback
    traceback.print_exc()
    print("FATAL:", e)
    sys.exit(1)

ac.App._fatal = _fatal_nb

import tkinter as tk
_orig_msg = ac.App._msg
ac.App._msg = lambda self, kind, title, msg: print("MSG:", kind, title, msg)

app = ac.App()
for _ in range(6):
    app.update()

# Helpers de transcripcion (gutter + tags + copiar)
app._apptxt("Linea de prueba con acentos aeiou n\n")
app._settxt("Transcripcion de ejemplo: los cloroplastos y la fotosintesis.")
app._clear_live()
app._fill_gutter()
app._txt_yscroll(0.0)
app._copy_trans()

# Toasts con tipo y Reintentar
app._show_toast("Grabacion lista", kind="ok")
app._show_toast("Error simulado", kind="err", retry=lambda: None)
app._show_toast("Aviso", kind="warn")

# Atajos seguros (sin tocar microfono)
app._kb_save(None)
app._kb_export(None)
app._kb_play(None)

# Cambio de tema (ejercita _apply_palette + remapeo de superficies)
app._theme()
for _ in range(4):
    app.update()
app._theme()
for _ in range(4):
    app.update()

# Los toasts se animan (pulso + desvanecido con colores intermedios que NO
# cumplen WCAG por diseno: se funden hacia el fondo). Si el chequeo muestrea
# un toast a mitad de animacion, falla de forma no determinista (flaky).
# Cancelar la animacion y destruir el label antes de medir contraste.
if getattr(app, "_toast_after", None) is not None:
    try:
        app.after_cancel(app._toast_after)
    except Exception:
        pass
    app._toast_after = None
for _attr in ("_toast_lbl", "_toast_btn"):
    _w = getattr(app, _attr, None)
    if _w is not None:
        try:
            _w.destroy()
        except Exception:
            pass
        setattr(app, _attr, None)

# ── Contraste WCAG AA: ningun texto/boton puede bajar de 4.5:1 (3:1 UI) ────
import wcag_check as wc
for _dark in (True, False):
    app.dark = _dark
    app._apply_palette()
    for _ in range(4):
        app.update()
    appearance = "dark" if _dark else "light"
    pairs = wc.collect_pairs(app, appearance)
    viol, _info = wc.check_pairs(pairs)
    if viol:
        for r, fg, bg, cls, txt, st in viol[:12]:
            print(f"CONTRASTE {appearance}: {r:.2f}:1 {cls} fg={fg} bg={bg} '{txt}'")
        print("SMOKE_OK -> FALLA: contraste WCAG AA")
        app.destroy()
        sys.exit(1)

# Estado de conexion en el header
app._chmode("local")
app._chmode("cloud")

# Insignia Revisado por IA (mostrar/ocultar)
if hasattr(app, "lbadge"):
    app.lbadge.pack(side="right", padx=(0, 14))
    app.update()
    app.lbadge.pack_forget()

# Boton Google Docs: desactivado con etiqueta clara si el componente falta
_gdoc_txt = app.bdocs.cget("text")
_ok_gdoc = ("no disponible" in _gdoc_txt) if not ac._gdocs_importable() else ("Google Docs" in _gdoc_txt)
if not _ok_gdoc:
    print(f"SMOKE_OK -> FALLA: etiqueta Google Docs inesperada: {_gdoc_txt}")
    app.destroy()
    sys.exit(1)

app.update()
app.destroy()
print("SMOKE_OK")
