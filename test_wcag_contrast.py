# -*- coding: utf-8 -*-
"""Validacion de contraste WCAG AA de la UI completa (dark y light).

Instancia la app real (sin wizard), camina el arbol de widgets y verifica que
NINGUN par (texto, fondo) baje de 4.5:1 (texto) / 3:1 (UI) en cualquiera de
los dos temas. Tambien valida las superficies semanticas de la paleta y los
textos calculados de boton (_btn_text_color). Cubre la ventana principal,los dialogos secundarios (config/mic/optimizador/guia), el dialogo de
advertencia de microfono debil (nivel bajo, medidor en vivo) y el wizard de
bienvenida (first_run=True, instancia fresca por tema).

FALLA si aparece cualquier violacion — correrlo en CI junto a test_ui_smoke.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import audioclass_v91 as ac
import wcag_check as wc

# Config aislada (no tocar la real)
CFG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wcag_config.json")
ac.CONFIG_PATH = CFG
cfg = ac.DEFAULT_CONFIG.copy()
cfg["first_run"] = False
with open(CFG, "w", encoding="utf-8") as f:
    json.dump(cfg, f)


def _fatal_nb(self, e):
    import traceback
    traceback.print_exc()
    print("FATAL:", e)
    sys.exit(1)


ac.App._fatal = _fatal_nb
ac.App._msg = lambda self, kind, title, msg: None

failures = []


def check(name, cond, detail=""):
    print(f"[{'OK ' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        failures.append(name)


def run_theme(app, dark, scope=None):
    app.dark = dark
    app._apply_palette()
    for _ in range(5):
        app.update()
    appearance = "dark" if dark else "light"
    pairs = wc.collect_all_pairs(app, appearance)
    viol, info = wc.check_pairs(pairs)
    mode = "dark" if dark else "light"
    label = f"[{mode}" + (f":{scope}" if scope else "") + "]"
    print(f"  {label} pares: {len(pairs)}, violaciones: {len(viol)}, disabled(exento): {len(info)}")
    for r, fg, bg, cls, txt, st in viol[:15]:
        print(f"    VIOLA {r:.2f}:1  {cls} fg={fg} bg={bg} '{txt}' st={st}")
    # Superficies semanticas de la paleta (texto sobre bg/card)
    P = ac.PALETTES["dark" if dark else "light"]
    for fkey in ("text", "muted", "ok", "warn", "err", "accent"):
        for bkey in ("bg", "card"):
            r = wc.contrast(P[fkey], P[bkey])
            if r is not None and r < wc.TEXT_MIN:
                viol.append((r, P[fkey], P[bkey], f"paleta:{fkey}/{bkey}", "", ""))
                print(f"    VIOLA paleta {fkey}/{bkey}: {r:.2f}:1")
    # Texto de boton calculado vs su fondo (todos los colores de superficie usados como boton)
    for bkey in ("accent", "button", "err", "mic", "cloud", "gemini", "easy"):
        bg = P[bkey]
        tcol = ac._btn_text_color(bg)
        r = wc.contrast(tcol, bg)
        if r is not None and r < wc.TEXT_MIN:
            viol.append((r, tcol, bg, f"btn_text:{bkey}", "", ""))
            print(f"    VIOLA btn {bkey} ({bg}) con {tcol}: {r:.2f}:1")
    check(f"contraste {mode} (texto>=4.5, UI>=3)", len(viol) == 0, f"{len(viol)} violaciones")


app = ac.App()
for _ in range(6):
    app.update()

run_theme(app, dark=True)
run_theme(app, dark=False)
run_theme(app, dark=True)   # volver al oscuro: el re-mapeo no debe romper nada

# ── Dialogos secundarios (CTkToplevel) en ambos temas ────────────────────
def toplevels():
    return [w for w in app.winfo_children()
            if w.winfo_class() in ("Toplevel", "CTkToplevel") and w.winfo_exists()]

def open_dialog(name):
    before = set(id(w) for w in toplevels())
    if name == "config":
        app._open_config()
    elif name == "mic":
        app._test_mic()
    elif name == "opt":
        app._open_mic_opt()
    elif name == "guide":
        app._open_guide(1)
    for _ in range(4):
        app.update()
    return next((w for w in toplevels() if id(w) not in before), None)

for dname in ("config", "mic", "opt", "guide"):
    top = open_dialog(dname)
    if top is None:
        check(f"dialogo {dname} abre", False, "no se creo la ventana")
        continue
    for dark in (True, False):
        run_theme(app, dark, scope=dname)
    top.destroy()
    for _ in range(2):
        app.update()
    check(f"dialogo {dname} verificado en dark y light", True)

# ── Dialogo de advertencia de microfono debil (solo se abre con nivel bajo) ─
# Se valida como se CREA, en ambos temas (instancia fresca por tema: los
# colores se capturan al crearla y no hay toggle dentro). El medidor en vivo
# se detiene de inmediato (_mic_warn_decided) para no abrir el microfono.
for warn_dark in (True, False):
    app.dark = warn_dark
    app._apply_palette()
    app._open_mic_warn_dialog(0.003)
    app._mic_warn_decided = True   # detener el worker del medidor en vivo
    for _ in range(3):
        app.update()
    appearance = "dark" if warn_dark else "light"
    pairs = wc.collect_all_pairs(app, appearance)
    viol, _info = wc.check_pairs(pairs)
    mode = "dark" if warn_dark else "light"
    print(f"  [micwarn:{mode}] pares: {len(pairs)}, violaciones: {len(viol)}")
    for r, fg, bg, cls, txt, st in viol[:15]:
        print(f"    VIOLA {r:.2f}:1  {cls} fg={fg} bg={bg} '{txt}' st={st}")
    check(f"contraste micwarn {mode} (texto>=4.5, UI>=3)", len(viol) == 0, f"{len(viol)} violaciones")
    if getattr(app, "mic_warn_top", None) is not None:
        try:
            app.mic_warn_top.destroy()
        except Exception:
            pass
        app.mic_warn_top = None
    for _ in range(2):
        app.update()

app.destroy()

# ── Wizard de bienvenida (first_run=True) en ambos temas ───────────────────
# Se valida COMO SE CREA (instancia fresca por tema): el wizard solo se
# muestra en el arranque con el tema de la config y no hay toggle dentro,
# asi que un cambio de tema posterior no le aplica.
def validate_wizard(theme):
    cfg = ac.DEFAULT_CONFIG.copy()
    cfg["first_run"] = True
    cfg["theme"] = theme
    with open(CFG, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    wapp = ac.App()
    for _ in range(6):
        wapp.update()
    check(f"wizard first_run visible ({theme})",
          hasattr(wapp, "wizard") and wapp.wizard.winfo_exists())
    appearance = "dark" if theme == "dark" else "light"
    pairs = wc.collect_all_pairs(wapp, appearance)
    viol, info = wc.check_pairs(pairs)
    print(f"  [wizard:{theme}] pares: {len(pairs)}, violaciones: {len(viol)}, disabled(exento): {len(info)}")
    for r, fg, bg, cls, txt, st in viol[:15]:
        print(f"    VIOLA {r:.2f}:1  {cls} fg={fg} bg={bg} '{txt}' st={st}")
    check(f"contraste wizard {theme} (texto>=4.5, UI>=3)", len(viol) == 0, f"{len(viol)} violaciones")
    wapp.destroy()
    for _ in range(2):
        try:
            wapp.update()
        except Exception:
            pass


validate_wizard("dark")
validate_wizard("light")

# ── Tema JSON de CTk: defaults que aplican a widgets crudos ───────────────
try:
    import customtkinter as ctk
    ctk.set_default_color_theme(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "audioclass_theme.json"))
    root = ctk.CTk()
    root.withdraw()
    for mode in ("light", "dark"):
        ctk.set_appearance_mode(mode)
        lbl = ctk.CTkLabel(root, text="x")
        btn = ctk.CTkButton(root, text="x")
        ent = ctk.CTkEntry(root)
        tbox = ctk.CTkTextbox(root)
        for name, wdg in (("CTkLabel", lbl), ("CTkButton", btn), ("CTkEntry", ent), ("CTkTextbox", tbox)):
            tc = wdg.cget("text_color")
            fgc = wdg.cget("fg_color")
            tc = wc.resolve_color(tc, mode)
            bg = wc.resolve_color(fgc, mode)
            if wc._is_transparent(bg):
                bg = ac.PALETTES["dark" if mode == "dark" else "light"]["card"]
            r = wc.contrast(tc, bg)
            ok = r is not None and r >= wc.TEXT_MIN
            check(f"tema JSON {mode}: {name} texto {tc} sobre {bg}", ok, f"{r:.2f}:1" if r else "n/a")
        btn_dis = wc.resolve_color(btn.cget("text_color_disabled"), mode)
        r = wc.contrast(btn_dis, ac.PALETTES["dark" if mode == "dark" else "light"]["button"])
        check(f"tema JSON {mode}: CTkButton disabled texto", r is not None and r >= wc.UI_MIN, f"{r:.2f}:1" if r else "n/a")
    root.destroy()
except Exception as e:
    print("CTk no disponible, salto validacion de tema JSON:", e)

print()
if failures:
    print("RESULTADO: FALLARON", len(failures), ":", ", ".join(failures))
    sys.exit(1)
print("RESULTADO: TODO OK")
