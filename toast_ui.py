"""
toast_ui.py — Toast notifications extraído de audioclass_v91.py
===============================================================

Mixin ``ToastMixin`` que encapsula el sistema de notificaciones toast
animadas (ok/err/warn) con soporte para botón de Reintentar.

Patrón idéntico a ``ConfigDialogMixin``: el mixin asume que ``self``
tiene los atributos que ``App`` ya expone (``self.steps_frame``,
``self.FH``, ``self.FB``, ``self._C``, ``self.after``, etc.).

Uso::

    from toast_ui import ToastMixin

    class App(ToastMixin, ...):
        ...

    app._show_toast("Transcripción completada", kind="ok")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

try:
    import customtkinter as ctk

    CTK = True
except ImportError:
    import tkinter as tk

    ctk = tk
    CTK = False

if TYPE_CHECKING:
    pass


class ToastMixin:
    """Mixin que proporciona notificaciones toast animadas."""

    def _show_toast(self, msg: str, kind: str = "ok", retry=None) -> None:
        """Muestra un toast animado (ok/err/warn) junto al indicador de pasos.

        kind='err' admite 'Reintentar': boton que invoca la callback retry.
        Animacion: entra deslizandose con pulso, permanece ~1.5 s y se desvanece.

        Args:
            msg: Mensaje a mostrar.
            kind: Tipo de toast ('ok', 'err', 'warn').
            retry: Callback opcional para el boton 'Reintentar'.
        """
        C = self._C
        if not hasattr(self, "steps_frame"):
            return
        try:
            if not self.steps_frame.winfo_exists():
                return
        except Exception:
            return

        # Limpiar un toast anterior que aun se estuviera animando
        if getattr(self, "_toast_after", None):
            try:
                self.after_cancel(self._toast_after)
            except Exception:
                pass
            self._toast_after = None
        if getattr(self, "_toast_lbl", None) is not None:
            try:
                self._toast_lbl.destroy()
            except Exception:
                pass
            self._toast_lbl = None
        if getattr(self, "_toast_btn", None) is not None:
            try:
                self._toast_btn.destroy()
            except Exception:
                pass
            self._toast_btn = None

        # Toasts: colores derivados de la paleta activa C para que siempre
        # tengan contraste y sigan el tema (claro/oscuro).
        _TOAST_STYLES = {
            "ok": {"bg_key": "card", "fg": C["ok"]},
            "err": {"bg_key": "card", "fg": C["err"]},
            "warn": {"bg_key": "card", "fg": C["warn"]},
        }
        style = _TOAST_STYLES.get(kind, _TOAST_STYLES["ok"])
        pill_bg = C.get(style["bg_key"], C["card"])
        pill_fg = style["fg"]
        pulse_col = C.get(kind, C["accent"])
        self._toast_btn = None

        if CTK:
            lbl = ctk.CTkLabel(
                self.steps_frame,
                text="[OK] " + msg,
                font=(self.FH, 12, "bold"),
                text_color=pill_fg,
                fg_color=pill_bg,
                corner_radius=10,
                padx=12,
                pady=3,
            )
        else:
            lbl = ctk.Label(
                self.steps_frame,
                text="[OK] " + msg,
                font=(self.FH, 12, "bold"),
                bg=pill_bg,
                fg=pill_fg,
                padx=12,
                pady=3,
            )
        lbl.pack(side="left", padx=(42, 0))
        self._toast_lbl = lbl
        color_opt = "text_color" if CTK else "fg"
        bg_opt = "fg_color" if CTK else "bg"
        page_bg = C["bg"]

        if retry is not None:

            def _do_retry():
                """Metodo interno: do retry."""
                for w_ in (self._toast_lbl, self._toast_btn):
                    try:
                        if w_ is not None:
                            w_.destroy()
                    except Exception:
                        pass
                self._toast_lbl = self._toast_btn = None
                if getattr(self, "_toast_after", None):
                    try:
                        self.after_cancel(self._toast_after)
                    except Exception:
                        pass
                    self._toast_after = None
                try:
                    retry()
                except Exception:
                    pass

            if CTK:
                rb = ctk.CTkButton(
                    self.steps_frame,
                    text="Reintentar",
                    command=_do_retry,
                    width=84,
                    height=26,
                    corner_radius=8,
                    font=(self.FH, 10, "bold"),
                    fg_color=pill_fg,
                    text_color=pill_bg,
                    hover_color=pulse_col,
                )
            else:
                rb = ctk.Button(
                    self.steps_frame,
                    text="Reintentar",
                    command=_do_retry,
                    bg=pill_fg,
                    fg=pill_bg,
                    font=(self.FB, 10, "bold"),
                )
            rb.pack(side="left", padx=(6, 0))
            self._toast_btn = rb

        def _lerp(c1, c2, t):
            """Metodo interno: lerp."""
            r1, g1, b1 = (int(c1[i : i + 2], 16) for i in (1, 3, 5))
            r2, g2, b2 = (int(c2[i : i + 2], 16) for i in (1, 3, 5))
            return "#%02x%02x%02x" % (
                int(r1 + (r2 - r1) * t),
                int(g1 + (g2 - g1) * t),
                int(b1 + (b2 - b1) * t),
            )

        def _pulse(step, total=8):
            """Metodo interno: pulse."""
            lbl2 = getattr(self, "_toast_lbl", None)
            if lbl2 is None or not lbl2.winfo_exists():
                return
            try:
                padx_left = max(8, 42 - int(34 * step / total))
                lbl2.pack_configure(padx=(padx_left, 0))
                lbl2.configure(**{color_opt: pulse_col if step % 2 == 0 else pill_fg})
            except Exception:
                return
            if step < total:
                self._toast_after = self.after(35, lambda: _pulse(step + 1))
            else:
                lbl2.configure(**{color_opt: pill_fg})
                self._toast_after = self.after(4500 if kind == "err" else 1500, _fade)

        def _fade(step=0, total=8):
            """Metodo interno: fade."""
            lbl2 = getattr(self, "_toast_lbl", None)
            if lbl2 is None or not lbl2.winfo_exists():
                return
            try:
                t = min(1.0, (step + 1) / total)
                lbl2.configure(
                    **{
                        color_opt: _lerp(pill_fg, pill_bg, t),
                        bg_opt: _lerp(pill_bg, page_bg, t),
                    }
                )
            except Exception:
                pass
            if step < total:
                self._toast_after = self.after(40, lambda: _fade(step + 1))
            else:
                try:
                    lbl2.destroy()
                except Exception:
                    pass
                self._toast_lbl = None
                self._toast_after = None
                if getattr(self, "_toast_btn", None) is not None:
                    try:
                        self._toast_btn.destroy()
                    except Exception:
                        pass
                    self._toast_btn = None

        self._toast_after = self.after(60, lambda: _pulse(0))
