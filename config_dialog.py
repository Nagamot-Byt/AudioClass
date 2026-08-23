#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_dialog.py — Diálogo de configuración extraído de audioclass_v91.py
=========================================================================

Mixin ``ConfigDialogMixin`` que encapsula la ventana de configuración
(Gemini/OpenAI keys, Colab URL, micrófono, Google Docs, privacidad).

Patrón idéntico a ``MicTestMixin`` / ``RecordingMixin``: el mixin asume
que ``self`` tiene los atributos y métodos que ``App`` ya expone
(``self.config``, ``self._frame()``, ``self._lbl()``, etc.).

Uso::

    from config_dialog import ConfigDialogMixin

    class App(ConfigDialogMixin, RecordingMixin, MicTestMixin, ctk.CTk):
        ...

    app.open_config_dialog()   # abre la ventana
"""
from __future__ import annotations

import tkinter as tk
import tkinter.filedialog as filedialog
from typing import TYPE_CHECKING, Any

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    CTK = False

if TYPE_CHECKING:
    pass  # Evita import circular; self se resuelve en runtime


class ConfigDialogMixin:
    """Mixin que añade ``open_config_dialog()`` a la clase App.

    Atributos requeridos en ``self``:
        config (dict)          – configuración persistente
        local_engine            – motor de transcripción local
        adapt_engine            – motor de adaptación (Gemini/OpenAI)
        cloud_engine            – motor Colab
        docs_exporter           – exportador Google Docs
        mode_var                – tk/StringVar del modo de transcripción
        _themeable (list)       – widgets que cambian con el tema

    Métodos requeridos en ``self``:
        _frame, _lbl, _entry, _btn  – helpers de widget
        _test_adapt()               – probar conexión de IA
        _test_mic()                 – abrir prueba de micrófono
        _connect_google()           – conectar con Google Docs
        _update_adapt_status()      – actualizar estado de adaptación
        _chmode()                   – cambiar modo de transcripción
        _msg()                      – mostrar mensaje
        _build_adapt_engine()       – construir motor de adaptación
        after()                     – tkinter after (heredado de Tk)
    """

    def open_config_dialog(self):
        """Abre la ventana de configuración de AudioClass."""
        # Lazy imports para evitar circular dependencies con audioclass_v91
        from audioclass_v91 import (
            _input_devices, _find_best_mic, _gdocs_importable,
            CloudColabEngine, GoogleDocsExporter,
        )
        from config_manager import save_config as _cm_save_config
        from audioclass_core import CloudColabEngine as _CCE, GoogleDocsExporter as _GDE

        C = self._C  # paleta activa

        top = ctk.CTkToplevel(self) if CTK else tk.Toplevel(self)
        top.title("Configuracion de AudioClass")
        try:
            _sh = top.winfo_screenheight()
            top.geometry("650x%d" % min(1060, max(560, _sh - 80)))
        except Exception:
            top.geometry("650x680")
        top.transient(self)
        top.grab_set()
        top.grid_rowconfigure(0, weight=1)
        top.grid_columnconfigure(0, weight=1)

        # ── Cuerpo DESPLAZABLE ──────────────────────────────────────────────
        if CTK:
            body = ctk.CTkScrollableFrame(top, fg_color=C["bg"], corner_radius=0,
                                          scrollbar_button_color=C["border"])
            body.grid(row=0, column=0, sticky="nsew")
        else:
            from tkinter import Canvas, Scrollbar
            canvas = Canvas(top, bg=C["bg"], highlightthickness=0)
            sbar = Scrollbar(top, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=sbar.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            sbar.grid(row=0, column=1, sticky="ns")
            body = tk.Frame(canvas, bg=C["bg"])
            body_id = canvas.create_window((0, 0), window=body, anchor="nw")

            def _on_body_conf(_e):
                canvas.configure(scrollregion=canvas.bbox("all"))
            body.bind("<Configure>", _on_body_conf)

            def _on_canvas_conf(e):
                canvas.itemconfigure(body_id, width=e.width)
            canvas.bind("<Configure>", _on_canvas_conf)
            canvas.bind("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
            body.bind("<MouseWheel>",
                      lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        self.cfg_body = body
        body.grid_columnconfigure(0, weight=1)

        # ── Sección: Proveedor de IA para análisis ──────────────────────────
        f1 = self._frame(body, fg_color=C["card"])
        f1.pack(fill="x", padx=20, pady=10)
        self._lbl(f1, "Proveedor de IA para el análisis",
                  font=(self.FH, 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f1,
                  "Elige con qué servicio analizar tus clases (resúmenes, guías, exámenes):",
                  font=(self.FB, 10), text_color=C["muted"]).pack(anchor="w", padx=15,
                                                                    pady=(0, 8))
        adapt_provider = ctk.StringVar(value=self.config.get("adapt_provider", "gemini"))
        prov_row = self._frame(f1, fg_color="transparent")
        prov_row.pack(anchor="w", padx=15, pady=(0, 8))
        for val, lbl in (("gemini", "Gemini (Google)"), ("openai", "OpenAI (GPT)")):
            rb = ctk.CTkRadioButton(prov_row, text=lbl, variable=adapt_provider,
                                    value=val, font=(self.FB, 11),
                                    text_color=C["text"])
            rb.pack(side="left", padx=(0, 25))
            self._themeable.append(("label", rb, "text"))

        # ── Sección Gemini ──
        f1g = self._frame(f1, fg_color="transparent")
        f1g.pack(fill="x", padx=15, pady=(0, 8))
        self._lbl(f1g, "API Key de Google AI Studio (Gemini)",
                  font=(self.FH, 12, "bold")).pack(anchor="w", pady=(4, 2))
        self._lbl(f1g, "Consiguela gratis en: aistudio.google.com/app/apikey",
                  font=(self.FB, 10), text_color=C["muted"]).pack(anchor="w", pady=(0, 4))
        gemini_entry = self._entry(f1g, width=500, font=(self.FB, 11))
        gemini_entry.pack(anchor="w", pady=(0, 4))
        gemini_entry.insert(0, self.config.get("gemini_api_key", ""))

        gemini_model = ctk.StringVar(value=self.config.get("gemini_model", "flash"))
        gmod_row = self._frame(f1g, fg_color="transparent")
        gmod_row.pack(anchor="w", pady=(0, 4))
        if CTK:
            for val, lbl in (("flash", "Flash"), ("pro", "Pro")):
                rb = ctk.CTkRadioButton(gmod_row, text=lbl, variable=gemini_model,
                                        value=val, font=(self.FB, 11),
                                        text_color=C["text"])
                rb.pack(side="left", padx=(0, 20))
                self._themeable.append(("label", rb, "text"))
        else:
            ctk.OptionMenu(f1g, gemini_model, "flash", "pro").pack(
                anchor="w", padx=15, pady=(0, 12))
        self._lbl(f1g,
                  "flash = rapido y economico (Gemini 2.0 Flash) | "
                  "pro = maxima calidad (Gemini 2.5 Pro)",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", pady=(0, 4))

        test_row = self._frame(f1g, fg_color="transparent")
        test_row.pack(fill="x", pady=(0, 4))
        self.gemini_test_lbl = self._lbl(test_row, "", font=(self.FB, 10),
                                         text_color=C["muted"])
        self.gemini_test_lbl.pack(side="left", padx=(0, 10))
        self.btn_test_gemini = self._btn(
            test_row, "Probar Conexión",
            lambda: self._test_adapt(gemini_entry, gemini_model, "gemini"),
            width=150, height=30, fg_color=C["accent"])
        self.btn_test_gemini.pack(side="left")

        # ── Sección OpenAI ──
        f1o = self._frame(f1, fg_color="transparent")
        f1o.pack(fill="x", padx=15, pady=(0, 8))
        self._lbl(f1o, "API Key de OpenAI (GPT)",
                  font=(self.FH, 12, "bold")).pack(anchor="w", pady=(4, 2))
        self._lbl(f1o,
                  "Consiguela en: platform.openai.com/api-keys "
                  "(tiene plan gratuito inicial)",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", pady=(0, 4))
        openai_entry = self._entry(f1o, width=500, font=(self.FB, 11))
        openai_entry.pack(anchor="w", pady=(0, 4))
        openai_entry.insert(0, self.config.get("openai_api_key", ""))

        openai_model = ctk.StringVar(value=self.config.get("openai_model", "mini"))
        omod_row = self._frame(f1o, fg_color="transparent")
        omod_row.pack(anchor="w", pady=(0, 4))
        for val, lbl in (("mini", "GPT-4o mini"), ("gpt4o", "GPT-4o")):
            rb = ctk.CTkRadioButton(omod_row, text=lbl, variable=openai_model,
                                    value=val, font=(self.FB, 11),
                                    text_color=C["text"])
            rb.pack(side="left", padx=(0, 20))
            self._themeable.append(("label", rb, "text"))
        self._lbl(f1o, "mini = rapido y economico | GPT-4o = maxima calidad",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", pady=(0, 4))

        otest_row = self._frame(f1o, fg_color="transparent")
        otest_row.pack(fill="x", pady=(0, 4))
        self.openai_test_lbl = self._lbl(otest_row, "", font=(self.FB, 10),
                                         text_color=C["muted"])
        self.openai_test_lbl.pack(side="left", padx=(0, 10))
        self.btn_test_openai = self._btn(
            otest_row, "Probar Conexión",
            lambda: self._test_adapt(openai_entry, openai_model, "openai"),
            width=150, height=30, fg_color=C["accent"])
        self.btn_test_openai.pack(side="left")

        # Auto-test solo del proveedor activo al abrir la ventana
        if self.config.get("adapt_provider", "gemini") == "openai":
            if self.config.get("openai_api_key"):
                self.after(400, lambda: self._test_adapt(
                    openai_entry, openai_model, "openai"))
        elif self.config.get("gemini_api_key"):
            self.after(400, lambda: self._test_adapt(
                gemini_entry, gemini_model, "gemini"))

        # ── Sección: Google Colab ──
        f2 = self._frame(body, fg_color=C["card"])
        f2.pack(fill="x", padx=20, pady=10)
        self._lbl(f2, "Google Colab (Cloud GPU)",
                  font=(self.FH, 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f2, "URL de ngrok desde tu servidor de Colab:",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", padx=15, pady=(0, 8))
        colab_entry = self._entry(f2, width=500, font=(self.FB, 11))
        colab_entry.pack(anchor="w", padx=15, pady=(0, 8))
        colab_entry.insert(0, self.config.get("colab_url", ""))

        colab_key = self._entry(f2, width=200, font=(self.FB, 11))
        colab_key.pack(anchor="w", padx=15, pady=(0, 12))
        colab_key.insert(0, self.config.get("colab_key", ""))

        # ── Sección: Micrófono ──
        fm = self._frame(body, fg_color=C["card"])
        fm.pack(fill="x", padx=20, pady=10)
        self._lbl(fm, "Micrófono de grabación",
                  font=(self.FH, 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(fm,
                  "Elige con qué micrófono grabar y medir el nivel. "
                  "Con 'Predeterminado del sistema' se usa el que Windows tenga activo.",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", padx=15, pady=(0, 8))
        mic_row = self._frame(fm, fg_color="transparent")
        mic_row.pack(fill="x", padx=15, pady=(0, 12))
        mic_devs = _input_devices()
        mic_names = ["Predeterminado del sistema"] + [n for _, n in mic_devs]
        cur_mic = str(self.config.get("mic_device") or "").strip()
        mic_var = ctk.StringVar(
            value=cur_mic if cur_mic in mic_names else "Predeterminado del sistema")
        if CTK:
            self.mic_menu = ctk.CTkOptionMenu(
                mic_row, values=mic_names, variable=mic_var,
                width=470, font=(self.FB, 11), fg_color=C["button"],
                text_color=C["text"], button_color=C["accent"],
                button_hover_color=C["accent_hover"],
                dropdown_fg_color=C["card"], dropdown_hover_color=C["border"],
                dropdown_text_color=C["text"])
        else:
            self.mic_menu = tk.OptionMenu(mic_row, mic_var, *mic_names)
        self.mic_menu.pack(side="left", padx=(0, 8))
        if not mic_devs:
            try:
                self.mic_menu.configure(state="disabled")
            except Exception:
                pass

        self._mic_search_lbl = self._lbl(mic_row, "", font=(self.FB, 10),
                                         text_color=C["muted"])
        self._mic_search_lbl.pack(side="left", padx=(8, 4))

        def _auto_find_mic():
            """Busca automaticamente el microfono con mejor senal."""
            try:
                import sounddevice as _sd
                self._mic_search_lbl.configure(
                    text="Buscando...", text_color=C["warn"])
                self.update_idletasks()
                best_id, best_p90 = _find_best_mic()
                if best_id is not None:
                    devs = _sd.query_devices()
                    if best_id < len(devs):
                        found_name = str(devs[best_id]["name"])
                        self.config["mic_device"] = found_name
                        _cm_save_config(self.config)
                        if hasattr(self, "mic_menu"):
                            try:
                                self.mic_menu.set(found_name)
                            except Exception:
                                pass
                        self._mic_search_lbl.configure(
                            text=f"Encontrado: {found_name[:30]} "
                                 f"(p90={best_p90:.4f})",
                            text_color=C["ok"])
                    else:
                        self._mic_search_lbl.configure(
                            text="No se encontro mic activo",
                            text_color=C["err"])
                else:
                    self._mic_search_lbl.configure(
                        text="No hay microfonos con senal",
                        text_color=C["err"])
            except Exception as ex:
                self._mic_search_lbl.configure(
                    text=f"Error: {str(ex)[:40]}", text_color=C["err"])

        self._btn(mic_row, "Auto-detectar", _auto_find_mic,
                  width=120, height=28,
                  fg_color=C["accent"], hover_color=C["accent_hover"]).pack(
            side="left", padx=(4, 0))

        # Control de ganancia del microfono
        gain_row = self._frame(fm, fg_color="transparent")
        gain_row.pack(fill="x", padx=15, pady=(0, 8))
        self._lbl(gain_row, "Ganancia del microfono:",
                  font=(self.FB, 11)).pack(side="left", padx=(0, 8))
        gain_var = ctk.DoubleVar(value=float(self.config.get("mic_gain", 1.0)))
        gain_lbl = self._lbl(gain_row, "1.0x", font=(self.FB, 10),
                             text_color=C["muted"])
        gain_lbl.pack(side="right", padx=(8, 0))

        def _on_gain_change(val):
            try:
                v = float(val)
                gain_lbl.configure(text=f"{v:.1f}x")
                self.config["mic_gain"] = v
            except Exception:
                pass

        if CTK:
            gain_slider = ctk.CTkSlider(
                gain_row, from_=1.0, to=5.0, number_of_steps=40,
                variable=gain_var, command=_on_gain_change,
                width=200, progress_color=C["accent"])
            gain_slider.pack(side="left", padx=(0, 8))
        else:
            from tkinter import Scale as _Scale
            gain_slider = _Scale(
                gain_row, from_=1.0, to=5.0, resolution=0.1,
                orient="horizontal", variable=gain_var,
                command=_on_gain_change, length=200)
            gain_slider.pack(side="left", padx=(0, 8))
        self._lbl(gain_row,
                  "(si tu microfono es muy subido, sube la ganancia)",
                  font=(self.FB, 9), text_color=C["muted"]).pack(side="left")

        # ── Sección: Prueba rápida de micrófono ──
        f0 = self._frame(body, fg_color=C["card"])
        f0.pack(fill="x", padx=20, pady=10)
        self._lbl(f0, "Prueba rapida de microfono",
                  font=(self.FH, 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f0,
                  "Graba 8 segundos y comprueba que tu microfono capta bien tu voz.",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", padx=15, pady=(0, 8))
        self._btn(f0, "Abrir prueba de microfono", self._test_mic,
                  width=240, height=36,
                  fg_color=C["err"], hover_color=C["err"]).pack(
            anchor="w", padx=15, pady=(0, 12))

        # ── Sección: Estado de Conexiones ──
        f3 = self._frame(body, fg_color=C["card"])
        f3.pack(fill="x", padx=20, pady=10)
        self._lbl(f3, "Estado de Conexiones",
                  font=(self.FH, 13, "bold")).pack(anchor="w", padx=15, pady=(12, 8))

        status_frame = self._frame(f3, fg_color="transparent")
        status_frame.pack(fill="x", padx=15, pady=(0, 12))

        self._lbl(status_frame, "Modelo Local:",
                  font=(self.FB, 11)).pack(side="left")
        self._lbl(status_frame,
                  "Listo" if self.local_engine.ready else "Cargando...",
                  font=(self.FB, 11),
                  text_color=C["ok"] if self.local_engine.ready else C["warn"]
                  ).pack(side="left", padx=(5, 20))

        self._lbl(status_frame, "Colab:",
                  font=(self.FB, 11)).pack(side="left")
        has_url = bool(self.config.get("colab_url"))
        self._lbl(status_frame,
                  "Configurado" if has_url else "Sin URL",
                  font=(self.FB, 11),
                  text_color=C["ok"] if has_url else C["err"]
                  ).pack(side="left", padx=(5, 20))

        self._lbl(status_frame, "Gemini:",
                  font=(self.FB, 11)).pack(side="left")
        has_key = bool(self.config.get("gemini_api_key"))
        self._lbl(status_frame,
                  "Configurado" if has_key else "Sin Key",
                  font=(self.FB, 11),
                  text_color=C["ok"] if has_key else C["err"]
                  ).pack(side="left", padx=5)

        self._lbl(status_frame, "OpenAI:",
                  font=(self.FB, 11)).pack(side="left")
        has_oai = bool(self.config.get("openai_api_key"))
        self._lbl(status_frame,
                  "Configurado" if has_oai else "Sin Key",
                  font=(self.FB, 11),
                  text_color=C["ok"] if has_oai else C["err"]
                  ).pack(side="left", padx=5)

        # ── Sección: Google Docs ──
        f4 = self._frame(body, fg_color=C["card"])
        f4.pack(fill="x", padx=20, pady=10)
        self._lbl(f4, "Google Docs (exportar transcripciones)",
                  font=(self.FH, 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f4,
                  "1. Crea credenciales OAuth en console.cloud.google.com "
                  "(tipo 'App de escritorio') y habilita la Docs API",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", padx=15, pady=(0, 2))
        self._lbl(f4,
                  "2. Descarga el client_secret.json y seleccionalo:",
                  font=(self.FB, 10), text_color=C["muted"]).pack(
            anchor="w", padx=15, pady=(0, 6))

        gdoc_row = self._frame(f4, fg_color="transparent")
        gdoc_row.pack(fill="x", padx=15, pady=(0, 8))
        gdoc_entry = self._entry(gdoc_row, width=380, font=(self.FB, 10))
        gdoc_entry.pack(side="left", padx=(0, 6))
        gdoc_entry.insert(0, self.config.get("google_creds_path", ""))

        def _pick_creds():
            fp = filedialog.askopenfilename(
                title="Selecciona client_secret.json",
                filetypes=[("Credenciales JSON", "*.json")])
            if fp:
                gdoc_entry.delete(0, "end")
                gdoc_entry.insert(0, fp)

        self._btn(gdoc_row, "Examinar...", _pick_creds,
                  width=100, height=30).pack(side="left", padx=(0, 10))
        self.btn_gdoc_connect = self._btn(
            gdoc_row, "Conectar con Google",
            lambda: self._connect_google(gdoc_entry.get().strip()),
            width=150, height=30, fg_color=C["ok"])
        self.btn_gdoc_connect.pack(side="left")

        self.gdoc_lbl = self._lbl(f4, "", font=(self.FB, 10))
        self.gdoc_lbl.pack(anchor="w", padx=15, pady=(0, 12))

        if not _gdocs_importable():
            try:
                self.btn_gdoc_connect.configure(state="disabled")
                self.gdoc_lbl.configure(
                    text="No disponible en esta versión: falta "
                         "google-auth-oauthlib (no incluido en el instalador).",
                    text_color=C["warn"])
            except Exception:
                pass
        else:
            try:
                gok, gmsg = self.docs_exporter.test_connection(refresh=False)
                self.gdoc_lbl.configure(
                    text=("[OK] " if gok else "· ") + gmsg,
                    text_color=C["ok"] if gok else C["muted"])
            except Exception:
                pass

        # ── Sección: Privacidad / consentimiento de IA ──
        fp = self._frame(f1, fg_color="transparent")
        fp.pack(fill="x", padx=15, pady=(8, 4))
        self._lbl(fp, "Privacidad",
                  font=(self.FH, 12, "bold")).pack(anchor="w", pady=(4, 2))
        self._lbl(fp,
                  "Las transcripciones se procesan en tu equipo. El análisis "
                  "con IA envía el texto a Gemini/OpenAI "
                  "(retención temporal del proveedor). El contenido generado "
                  "por IA puede contener errores y no es consejo médico/legal "
                  "ni acta oficial.",
                  font=(self.FB, 10), text_color=C["muted"],
                  wraplength=560, justify="left").pack(anchor="w", pady=(0, 4))
        ia_consent_var = ctk.BooleanVar(
            value=bool(self.config.get("ia_consent", False)))
        if CTK:
            ctk.CTkCheckBox(
                fp,
                text="Permito el análisis con IA (envío de mis "
                     "transcripciones a Gemini/OpenAI)",
                variable=ia_consent_var, font=(self.FB, 11),
                fg_color=C["accent"]).pack(anchor="w", pady=(0, 10))
        else:
            tk.Checkbutton(
                fp,
                text="Permito el analisis con IA (envio a Gemini/OpenAI)",
                variable=ia_consent_var, bg=C["card"], fg=C["text"],
                selectcolor=C["accent"]).pack(anchor="w", pady=(0, 10))

        # ── Función save ────────────────────────────────────────────────────
        def save():
            self.config["adapt_provider"] = adapt_provider.get()
            self.config["gemini_api_key"] = gemini_entry.get().strip()
            self.config["gemini_model"] = gemini_model.get()
            self.config["openai_api_key"] = openai_entry.get().strip()
            self.config["openai_model"] = openai_model.get()
            self.config["colab_url"] = colab_entry.get().strip()
            self.config["colab_key"] = colab_key.get().strip()
            self.config["google_creds_path"] = gdoc_entry.get().strip()
            mic_sel = mic_var.get()
            self.config["mic_device"] = (
                "" if mic_sel == "Predeterminado del sistema" else mic_sel)
            self.config["ia_consent"] = bool(ia_consent_var.get())
            _cm_save_config(self.config)

            self.adapt_engine = self._build_adapt_engine()
            self.cloud_engine = _CCE(
                self.config["colab_url"], self.config["colab_key"],
                self.config.get("whisper_language", "auto"))
            self.docs_exporter = _GDE(
                self.config["google_creds_path"])
            self._update_adapt_status()
            self._chmode(self.mode_var.get())
            top.destroy()
            self._msg("info", "Guardado",
                      "Configuracion actualizada correctamente.")

        # Barra de acciones SIEMPRE visible
        bar = self._frame(top, fg_color=C["card"],
                          border_width=1, border_color=C["border"])
        bar.grid(row=1, column=0, sticky="ew")
        self._btn(bar, "Guardar Cambios", save,
                  width=200, height=40,
                  fg_color=C["accent"]).pack(pady=12)
