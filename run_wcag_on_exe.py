# -*- coding: utf-8 -*-
"""Valida el contraste WCAG sobre el CODIGO EMPAQUETADO en el exe.

1. Extrae audioclass_v91 del CArchive del exe (bytecode marshal).
2. Lo importa como modulo 'audioclass_v91' (sys.modules['audioclass_v91']).
3. Replica la logica de test_wcag_contrast (sin tocar la config real del
   usuario) sobre ese modulo, en dark y light: principal + dialogo de config
   + wizard de bienvenida (first_run=True, instancia fresca por tema).
"""
import os
import sys
import json
import io
import marshal

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from PyInstaller.archive.readers import CArchiveReader

EXE = os.path.join(ROOT, "dist_onefile", "AudioClass.exe")
c = CArchiveReader(EXE)
code = marshal.loads(c.extract("audioclass_v91"))

# ── 1) Marcas de los fixes de contraste en el bytecode ────────────────────
import types
strings = set()
def walk(cd):
    for const in cd.co_consts:
        if isinstance(const, str):
            strings.add(const)
        elif isinstance(const, types.CodeType):
            walk(const)
    for n in cd.co_names:
        strings.add(n)
walk(code)
CODE_MARKERS = {
    "head_text (fix header claro)": "head_text",
    "theme_key forzado": "theme_key",
    "radio Local/Cloud (fix segmented)": "RadioButton",
    "radio Flash/Pro (fix config)": "Flash",
}
print("=== Marcas de fixes en el bytecode del exe ===")
bad = False
for label, m in CODE_MARKERS.items():
    ok = any(m in s for s in strings)
    print(f"  [{'OK ' if ok else 'NO '}] {label} ({m!r})")
    bad = bad or not ok

# ── 2) Tema JSON empaquetado identico al fuente ────────────────────────────
import zipimport  # noqa: F401 (para no romper la importacion de abajo)
entry_theme = r"assets\audioclass_theme.json"
exe_theme = json.loads(c.extract(entry_theme).decode("utf-8"))
with open(os.path.join(ROOT, "assets", "audioclass_theme.json"), encoding="utf-8") as f:
    cur_theme = json.load(f)
print("\n=== Tema JSON del exe ===")
print("  [%s] JSON empaquetado identico al fuente" % ("OK " if exe_theme == cur_theme else "NO "))
bad = bad or exe_theme != cur_theme

# ── 3) Ejecutar la validacion de contraste sobre el modulo del exe ────────
print("\n=== Contraste WCAG sobre el codigo del exe (dark y light) ===")
sys.modules["audioclass_v91"] = types.ModuleType("audioclass_v91")
mod = sys.modules["audioclass_v91"]
mod.__file__ = os.path.join(ROOT, "audioclass_v91.py")
mod.__package__ = ""
exec(code, mod.__dict__)
ac = mod

CFG = os.path.join(ROOT, "_wcag_exe_config.json")
ac.CONFIG_PATH = CFG
cfg = ac.DEFAULT_CONFIG.copy()
cfg["first_run"] = False
with open(CFG, "w", encoding="utf-8") as f:
    json.dump(cfg, f)
ac.App._fatal = lambda self, e: (_ for _ in ()).throw(RuntimeError(f"FATAL: {e}"))
ac.App._msg = lambda self, kind, title, msg: None

import wcag_check as wc

def run_theme(app, dark, scope=""):
    app.dark = dark
    app._apply_palette()
    for _ in range(5):
        app.update()
    appearance = "dark" if dark else "light"
    pairs = wc.collect_all_pairs(app, appearance)
    viol, info = wc.check_pairs(pairs)
    tag = ("dark" if dark else "light") + (":" + scope if scope else "")
    print(f"  [{tag}] pares={len(pairs)} violaciones={len(viol)} disabled_exentos={len(info)}")
    for r, fg, bg, cls, txt, st in viol[:10]:
        print(f"    VIOLA {r:.2f}:1 {cls} fg={fg} bg={bg} '{txt}'")
    return len(viol)

app = ac.App()
for _ in range(6):
    app.update()

total = 0
total += run_theme(app, True)
total += run_theme(app, False)
total += run_theme(app, True)

# Dialogo de configuracion (el que tenia las violaciones)
before = {id(w) for w in app.winfo_children() if w.winfo_class() in ("Toplevel", "CTkToplevel")}
app._open_config()
for _ in range(4):
    app.update()
top = next((w for w in app.winfo_children() if id(w) not in before), None)
if top is not None:
    total += run_theme(app, True, "config")
    total += run_theme(app, False, "config")
    top.destroy()
    for _ in range(2):
        app.update()
app.destroy()

# Wizard de bienvenida (first_run=True): se valida COMO SE CREA, con una
# instancia fresca por tema (el wizard solo se muestra en el arranque con el
# tema de la config; no hay toggle dentro).
def run_wizard(theme):
    cfg = ac.DEFAULT_CONFIG.copy()
    cfg["first_run"] = True
    cfg["theme"] = theme
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    wapp = ac.App()
    for _ in range(6):
        wapp.update()
    appearance = "dark" if theme == "dark" else "light"
    pairs = wc.collect_all_pairs(wapp, appearance)
    viol, info = wc.check_pairs(pairs)
    print(f"  [wizard:{theme}] pares={len(pairs)} violaciones={len(viol)} disabled_exentos={len(info)}")
    for r, fg, bg, cls, txt, st in viol[:10]:
        print(f"    VIOLA {r:.2f}:1 {cls} fg={fg} bg={bg} '{txt}'")
    wapp.destroy()
    return len(viol)

total += run_wizard("dark")
total += run_wizard("light")

print()
if bad or total > 0:
    print(f"RESULTADO: FALLA (marcas={'NO' if bad else 'OK'}, violaciones={total})")
    sys.exit(1)
print("RESULTADO: TODO OK — los fixes de contraste sobreviven al empaquetado")
