# -*- coding: utf-8 -*-
"""Verificacion de contraste WCAG AA para la UI de AudioClass.

Reutilizable desde los tests (test_wcag_contrast.py, test_ui_smoke.py):
- calcula luminancia/contraste a partir de hex o tuplas RGB (los widgets CTk
  devuelven tuplas cuando appearance_mode esta activo),
- camina el arbol de widgets vivos y extrae pares (fg, bg) resolviendo fondos
  'transparent' por la cadena de padres,
- valida texto normal >= 4.5:1 y componentes/UI >= 3:1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TEXT_MIN = 4.5   # WCAG AA texto normal
UI_MIN = 3.0     # WCAG AA componentes / UI


def _channel(v):
    """Normaliza un canal (int 0-255 o float 0-1) a float 0-1."""
    v = float(v)
    return v / 255.0 if v > 1.0 else v


def _linear(c):
    c = _channel(c)
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(color):
    """Luminancia relativa WCAG de un color hex ('#RRGGBB') o tupla RGB."""
    if isinstance(color, str):
        color = color.strip()
        if color.startswith("#"):
            h = color[1:]
            if len(h) == 3:
                h = "".join(ch * 2 for ch in h)
            rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        elif color.startswith("gray"):
            # 'gray60' etc. -> escala Tk 0-100
            v = int(color[4:]) * 255 // 100
            rgb = (v, v, v)
        elif color.startswith("system"):
            return None
        else:
            return None
    elif isinstance(color, (tuple, list)) and len(color) >= 3:
        rgb = tuple(color[:3])
    else:
        return None
    return 0.2126 * _linear(rgb[0]) + 0.7152 * _linear(rgb[1]) + 0.0722 * _linear(rgb[2])


def contrast(a, b):
    """Ratio de contraste WCAG entre dos colores (None si no calculable)."""
    la, lb = luminance(a), luminance(b)
    if la is None or lb is None:
        return None
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def resolve_color(value, appearance):
    """CTk devuelve [light, dark]; resolver por el modo activo."""
    if isinstance(value, (tuple, list)) and len(value) == 2 and isinstance(value[0], str):
        return value[0] if appearance == "light" else value[1]
    if isinstance(value, (tuple, list)) and len(value) == 3 and all(isinstance(v, (int, float)) for v in value):
        return tuple(int(v) for v in value)
    return value


def _is_transparent(c):
    return c is None or (isinstance(c, str) and c.lower() in ("transparent", ""))


def effective_bg(w, appearance, max_depth=8):
    """Fondo efectivo de un widget resolviendo 'transparent' por la cadena de padres."""
    cur = w
    for _ in range(max_depth):
        if cur is None:
            return None
        cls = ""
        try:
            cls = cur.winfo_class()
        except Exception:
            return None
        bg = None
        try:
            if cls.startswith("CTk"):
                v = cur.cget("fg_color")
                bg = resolve_color(v, appearance)
            else:
                try:
                    bg = cur.cget("bg")
                except Exception:
                    # Controles CTk basados en tkinter.Frame (CTkButton,
                    # CTkFrame, CTkScrollableFrame...): 'bg' no es soportado
                    # por cget; su superficie real es el fg_color.
                    v = cur.cget("fg_color")
                    bg = resolve_color(v, appearance)
        except Exception:
            bg = None
        if not _is_transparent(bg):
            return bg
        cur = cur.master
    return None


def _frame_kind(widget):
    """Tipo de widget CTk implementado como tkinter.Frame (CTk 6):
    'button', 'radio', 'checkbox' o 'switch' (None si no es ninguno).
    Se detecta por isinstance (no por cget: '_text' lanza ValueError en
    radios/checkbox). Importante para el fondo: los controles de seleccion
    pintan su TEXTO sobre el fondo del PADRE (su fg_color es solo el
    circulo/cuadro/boton de estado), mientras que el CTkButton pinta su
    texto sobre su propio fg_color."""
    try:
        import customtkinter as ctk
        if isinstance(widget, ctk.CTkButton):
            return "button"
        if isinstance(widget, ctk.CTkRadioButton):
            return "radio"
        if isinstance(widget, ctk.CTkCheckBox):
            return "checkbox"
        if isinstance(widget, ctk.CTkSwitch):
            return "switch"
    except Exception:
        pass
    return None


def collect_pairs(w, appearance):
    """Camina el arbol y devuelve pares (fg, bg, clase, texto, estado)."""
    pairs = []

    def _widget_state(widget):
        try:
            st = str(widget.cget("state"))
        except Exception:
            st = ""
        # El estado del Label interno de un CTkButton vive en el Frame padre
        if "disabled" not in st:
            try:
                pst = str(widget.master.cget("state"))
                if "disabled" in pst:
                    st = pst
            except Exception:
                pass
        return st

    def walk(widget, depth=0):
        if depth > 8:
            return
        try:
            cls = widget.winfo_class()
        except Exception:
            return
        kind = _frame_kind(widget) if cls == "Frame" else None
        try:
            if cls.startswith("CTk") or kind is not None:
                tc = widget.cget("text_color")
                tc = resolve_color(tc, appearance)
                if not _is_transparent(tc):
                    # radio/checkbox/switch: el texto vive sobre el fondo del
                    # padre (el fg_color propio es solo el estado seleccionado)
                    if kind in ("radio", "checkbox", "switch"):
                        bg = effective_bg(widget.master, appearance)
                    else:
                        bg = effective_bg(widget, appearance)
                    txt = ""
                    try:
                        txt = str(widget.cget("text"))[:30]
                    except Exception:
                        pass
                    st = _widget_state(widget)
                    pairs.append((tc, bg, cls, txt, st))
                    # Botones: el color disabled tambien debe tener contraste
                    if kind == "button" or cls == "CTkButton":
                        try:
                            tcd = widget.cget("text_color_disabled")
                            tcd = resolve_color(tcd, appearance)
                            if not _is_transparent(tcd):
                                pairs.append((tcd, bg, cls + ":disabled", txt, "disabled"))
                        except Exception:
                            pass
            elif cls in ("Label", "Button", "Checkbutton", "Radiobutton", "Entry", "Text", "Menu"):
                # Saltar los Labels internos de los controles CTk (button/radio/
                # checkbox/switch): ya se recogen con el par correcto arriba.
                try:
                    if _frame_kind(widget.master) is not None:
                        return
                except Exception:
                    pass
                fg = widget.cget("fg")
                bg = widget.cget("bg")
                if not _is_transparent(fg) and not _is_transparent(bg):
                    txt = ""
                    try:
                        txt = str(widget.cget("text"))[:30]
                    except Exception:
                        pass
                    pairs.append((fg, bg, cls, txt, _widget_state(widget)))
        except Exception:
            pass
        for ch in widget.winfo_children():
            walk(ch, depth + 1)

    walk(w)
    return pairs


def collect_all_pairs(root, appearance):
    """Recoge los pares del widget raiz Y de todas sus ventanas hijas
    (CTkToplevel/Toplevel: configuracion, prueba de microfono, guia rapida)."""
    pairs = list(collect_pairs(root, appearance))
    try:
        for top in root.winfo_children():
            if top.winfo_class() in ("Toplevel", "CTkToplevel"):
                pairs.extend(collect_pairs(top, appearance))
    except Exception:
        pass
    return pairs


def check_pairs(pairs, min_text=TEXT_MIN, min_ui=UI_MIN, skip_disabled=True):
    """Devuelve (violaciones, info). Los widgets disabled estan EXENTOS de
    contraste en WCAG 1.4.3 (los componentes inactivos no lo requieren), asi
    que se omiten de las violaciones pero se devuelven como informativos."""
    violations, info = [], []
    for fg, bg, cls, txt, st in pairs:
        r = contrast(fg, bg)
        if r is None:
            continue
        if skip_disabled and ("disabled" in st or cls.endswith(":disabled")):
            info.append((r, fg, bg, cls, txt, st))
            continue
        # 4.5:1 para texto normal; 3:1 para componentes grandes/UI. Un boton
        # es componente UI, pero su texto debe leerse -> exigimos 4.5 cuando
        # el par es claramente texto (labels/entry/textbox) y 3 para el resto.
        is_text = cls.startswith(("CTkLabel", "CTkEntry", "CTkTextbox")) or cls in ("Label", "Entry", "Text", "Checkbutton", "Radiobutton")
        limit = min_text if is_text else min_ui
        if r < limit:
            violations.append((r, fg, bg, cls, txt, st))
    return violations, info
