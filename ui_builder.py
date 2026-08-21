#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_builder.py — Construccion de la interfaz de usuario
======================================================

Extrae la construccion de widgets de audioclass_v91.py en funciones puras
que reciben la instancia de App y construyen secciones de la UI.

Cada funcion ``build_<section>(app)`` crea los widgets de una zona concreta
y los asigna como atributos en ``app`` (patron intermediario entre un builder
puro y un mixin: mantiene el contrato de ``self.*`` sin duplicar logica).

Secciones extraidas:
- sidebar: barra lateral historial + botones
- header: cabecera de marca + pasos guiados + banner
- easy_mode: modo facil (switch + plantilla)
- controls: REC / Detener / Transcribir / Guardar
- vu_meter: medidor de nivel de entrada
- config_bar: perfil / motor / modelo / idioma / switches
- progress: barra de progreso
- waveform: grafico de onda
- adapt: adaptacion inteligente (botones + texto)
- transcription: editor de transcripcion
- footer: barra inferior (carpeta, atajos, reloj)
"""

from __future__ import annotations

import tkinter as tk
import tkinter.scrolledtext as scrolledtext
from typing import TYPE_CHECKING

from audioclass_core import (
    AudioPipeline, VISUAL_SAMPLES, OUTPUT_DIR,
)

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    CTK = False

try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL = True
except ImportError:
    MPL = False

if TYPE_CHECKING:
    from audioclass_v91 import App

# Alias de la paleta global para este modulo
try:
    from audioclass_v91 import C, PALETTES, _btn_text_color, GeminiAdaptationEngine, _gdocs_importable
except ImportError:
    C = {}
    PALETTES = {}
    def _btn_text_color(bg): return "#FFFFFF"
    class GeminiAdaptationEngine:
        TEMPLATES = {}
    def _gdocs_importable(): return False


# ---------------------------------------------------------------------------
# Sidebar (historial + botones de accion)
# ---------------------------------------------------------------------------

def build_sidebar(app: "App"):
    """Construye la barra lateral izquierda: historial de clases + botones."""
    mn = app  # App es el root

    sb = app._frame(mn, width=300, fg_color=C["card"])
    sb.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(15, 8),
            pady=8 if getattr(app, "_compact", False) else 15)
    sb.grid_propagate(False)

    app._lbl(sb, " Historial de Clases", font=(app.FH, 16, "bold"),
             text_color=C["text"]).pack(pady=(18, 12), padx=15, anchor="w")

    if CTK:
        hf = ctk.CTkScrollableFrame(sb, corner_radius=8, fg_color=C["card"])
    else:
        hf = tk.Frame(sb, bg=C["card"])
    hf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    app.hist_frame = hf

    bf = app._frame(sb, fg_color="transparent")
    bf.pack(fill="x", padx=10, pady=(0, 15))

    app.bplay = app._btn(bf, "Reproducir", app._play, state="disabled",
                          width=260, height=32, fg_color=C["accent"])
    app.bplay.pack(fill="x", pady=(0, 6))
    app.btransh = app._btn(bf, "Transcribir", app._transh, state="disabled",
                            width=260, height=32)
    app.btransh.pack(fill="x", pady=(0, 6))
    app.bdel = app._btn(bf, "Eliminar", app._delh, state="disabled",
                          width=260, height=32, fg_color=C["err"], hover_color=C["err"])
    app.bdel.pack(fill="x", pady=(0, 6))
    app.bcompile = app._btn(bf, "Compilar Todo", app._compile, state="disabled",
                              width=260, height=32, fg_color=C["cloud"], hover_color=C["cloud"])
    app.bcompile.pack(fill="x", pady=(0, 6))
    app.bguide = app._btn(bf, "Guia Rapida", app._open_guide, width=260, height=32,
                            fg_color=C["accent"], hover_color=C["accent_hover"])
    app.bguide.pack(fill="x", pady=(0, 6))
    app.bconfig = app._btn(bf, "Configuracion", app._open_config, width=260, height=32)
    app.bconfig.pack(fill="x", pady=(0, 6))
    app.badv = app._btn(bf, "Opciones avanzadas", app._toggle_advanced, width=260, height=32,
                          fg_color=C["cloud"], hover_color=C["cloud"])
    app.badv.pack(fill="x")


# ---------------------------------------------------------------------------
# Header (marca + pasos guiados + banner siguiente paso)
# ---------------------------------------------------------------------------

def build_header(app: "App", parent):
    """Construye la cabecera: logo, pasos del flujo, banner 'Siguiente paso'."""
    hd = app._frame(parent, fg_color=C["header"], border_width=1,
                     border_color=C["border"], theme_key="header")
    hd.grid(row=0, column=0, sticky="ew", padx=22, pady=(12, 6))
    hd.grid_columnconfigure(0, weight=1)

    # Marca
    brand = app._frame(hd, fg_color="transparent")
    brand.grid(row=0, column=0, sticky="w", padx=(18, 8), pady=(1, 0))
    app._lbl(brand, "AC", font=(app.FH, 24), text_color=C["head_text"],
             theme_key="head_text").pack(side="left", padx=(0, 12))
    btb = app._frame(brand, fg_color="transparent")
    btb.pack(side="left")
    app._lbl(btb, app.app_name if hasattr(app, "app_name") else "AudioClass",
             font=(app.FH, 21, "bold"), text_color=C["head_text"],
             theme_key="head_text").pack(anchor="w")
    app._lbl(btb, "Grabacion y transcripcion academica con IA",
             font=(app.FB, 11), text_color=C["head_text"],
             theme_key="head_text").pack(anchor="w")

    # Lado derecho del header
    hdr = app._frame(hd, fg_color="transparent")
    hdr.grid(row=0, column=1, sticky="e", padx=(8, 16), pady=(8, 2))
    app.lconn = app._lbl(hdr, "Motor local", font=(app.FB, 11),
                          text_color=C["head_text"], theme_key="head_text")
    app.lconn.pack(side="left", padx=(0, 12))
    app.btheme_hd = app._btn(hdr, "Tema", app._theme, width=44, height=34,
                              font=(app.FB, 14), fg_color=C["card"],
                              hover_color=C["border"])
    app.btheme_hd.pack(side="left")

    # Linea dorada
    app.goldline = (ctk.CTkFrame(hd, height=3, corner_radius=2, fg_color=C["accent"])
                    if CTK else tk.Frame(hd, height=3, bg=C["accent"]))
    app.goldline.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 8))
    try:
        app.goldline.grid_propagate(False)
    except Exception:
        pass

    # Pasos del flujo guiado
    steps = app._frame(hd, fg_color="transparent")
    steps.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(2, 0))
    app.steps_frame = steps
    app.step_lbls = {}
    for i, (num, txt) in enumerate([("1", "Graba"), ("2", "Transcribe"),
                                      ("3", "Analiza"), ("4", "Guarda")]):
        paso = i + 1
        if CTK:
            lbl = ctk.CTkLabel(steps, text=f"  {num}. {txt}  ",
                                font=(app.FB, 12, "bold"),
                                text_color=C["muted"], fg_color=C["button"],
                                corner_radius=12)
        else:
            lbl = tk.Label(steps, text=f"  {num}. {txt}  ",
                            font=(app.FB, 12, "bold"),
                            bg=C["button"], fg=C["muted"])
        lbl.pack(side="left", padx=(0, 14))
        lbl.bind("<Button-1>", lambda e, s=paso: app._open_guide(s))
        try:
            lbl.configure(cursor="hand2")
        except Exception:
            pass
        app.step_lbls[paso] = lbl
    app._set_step(1)

    # Banner "Siguiente paso"
    app.next_step_frame = None
    if not getattr(app, "_compact", False):
        nx = app._frame(hd, fg_color=C["card"], border_width=2,
                         border_color=C["accent"])
        nx.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 2))
        nx.grid_columnconfigure(0, weight=1)
        app.next_step_frame = nx
        app.lnext = app._lbl(nx, "", font=(app.FH, 15, "bold"),
                               text_color=C["accent"], anchor="w", wraplength=1000)
        app.lnext.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=(6, 2))
        app.lnext_sub = app._lbl(nx, "", font=(app.FB, 11), text_color=C["muted"],
                                   anchor="w", wraplength=1000)
        app.lnext_sub.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 2))
        app._btn(nx, "Como se hace?",
                  lambda: app._open_guide(app._next_guide_step or 1),
                  width=170, height=32, font=(app.FB, 11),
                  fg_color=C["accent"], hover_color=C["accent_hover"]
                  ).grid(row=0, column=1, rowspan=2, padx=(8, 16), pady=6)


# ---------------------------------------------------------------------------
# Modo Facil
# ---------------------------------------------------------------------------

def build_easy_mode(app: "App", parent):
    """Construye la seccion de Modo Facil (switch + plantilla)."""
    easy = app._frame(parent, fg_color=C["card"], border_width=2, border_color=C["easy"])
    easy.grid(row=1, column=0, sticky="ew", padx=22, pady=10)

    app._lbl(easy, "MODO FACIL", font=(app.FH, 16, "bold"),
             text_color=C["easy"]).pack(anchor="w", padx=18, pady=(2, 2))
    if not getattr(app, "_compact", False):
        app._lbl(easy, "Un solo boton hace TODO: Grabar -> Procesar -> Transcribir -> Analizar",
                  font=(app.FB, 11), text_color=C["muted"]).pack(anchor="w", padx=18, pady=(0, 4))

    easy_row = app._frame(easy, fg_color="transparent")
    easy_row.pack(fill="x", padx=18, pady=(0, 3))

    app.easy_var = ctk.BooleanVar(value=app.config.get("modo_facil", False))
    if CTK:
        app.easy_switch = ctk.CTkSwitch(easy_row, text="Activar Modo Facil",
                                         variable=app.easy_var, font=(app.FB, 12),
                                         command=app._toggle_easy,
                                         progress_color=C["easy"], button_color=C["easy"])
        app.easy_switch.pack(side="left", padx=(0, 20))
    else:
        app.easy_switch = tk.Checkbutton(easy_row, text="Activar Modo Facil",
                                          variable=app.easy_var, bg=C["card"],
                                          fg=C["text"], command=app._toggle_easy)
        app.easy_switch.pack(side="left", padx=(0, 20))

    app.easy_template = ctk.StringVar(
        value=app.config.get("adaptacion_default", "Analisis Academico Profundo"))
    templates_list = list(GeminiAdaptationEngine.TEMPLATES.keys())
    if CTK:
        app.easy_menu = ctk.CTkOptionMenu(easy_row, values=templates_list,
                                           variable=app.easy_template, width=260,
                                           font=(app.FB, 11))
        app.easy_menu.pack(side="left", padx=(0, 10))
    else:
        app.easy_menu = tk.OptionMenu(easy_row, app.easy_template, *templates_list)
        app.easy_menu.pack(side="left", padx=(0, 10))

    app._lbl(easy_row, "Selecciona que generar automaticamente",
              font=(app.FB, 10), text_color=C["muted"]).pack(side="left")


# ---------------------------------------------------------------------------
# Controles principales (REC, Detener, Transcribir, Guardar, etc.)
# ---------------------------------------------------------------------------

def build_controls(app: "App", parent):
    """Construye la fila de controles principales: REC, Detener, Transcribir, PDF, DOCX."""
    ct = app._frame(parent, fg_color=C["card"])
    ct.grid(row=2, column=0, sticky="ew", padx=22, pady=10)

    app.brec = app._btn(ct, "REC", app._togglerec, width=64, height=64,
                         corner_radius=32, font=(app.FB, 26), fg_color=C["mic"],
                         hover_color=C["err"], no_theme=True)
    app.brec.pack(side="left", padx=(18, 12), pady=10)

    app.bstop = app._btn(ct, "Detener", app._stoprec, width=150, height=52,
                          font=(app.FB, 14, "bold"), fg_color=C["err"],
                          hover_color=C["err"])
    app.bstop.pack(side="left", padx=(0, 12), pady=10)
    app.bstop.pack_forget()

    app.btr = app._btn(ct, "Transcribir", lambda: app._starttrans(False),
                        width=150, height=42, state="disabled")
    app.btr.pack(side="left", padx=(0, 8), pady=10)
    app.bts = app._btn(ct, "Con tiempos", lambda: app._starttrans(True),
                        width=130, height=42, state="disabled")
    app.bts.pack(side="left", padx=(0, 8), pady=10)
    app.bpdf = app._btn(ct, "Guardar PDF", app._pdf, width=130, height=42,
                         state="disabled")
    app.bpdf.pack(side="left", padx=(0, 8), pady=10)
    app.bdocx = app._btn(ct, "Guardar DOCX", app._export_docx, width=140, height=42,
                           state="disabled")
    app.bdocx.pack(side="left", padx=(0, 8), pady=10)
    app.bdocs = app._btn(ct, "Google Docs", app._export_docs, width=140, height=42,
                           state="disabled", fg_color=C["ok"], hover_color=C["ok"])
    if not _gdocs_importable():
        app.bdocs.configure(text="Google Docs (no disponible)", width=180)
    app.bdocs.pack(side="left", padx=(0, 8), pady=10)
    app.bcancel = app._btn(ct, "Cancelar", app._cancel, width=100, height=42,
                            state="disabled", fg_color=C["err"], hover_color=C["err"])
    app.bcancel.pack(side="left", padx=(0, 18), pady=10)

    # VU meter inline
    build_vu_meter(app, ct)

    # Estado
    app.lstatus = app._lbl(ct, "Listo para grabar", font=(app.FB, 12),
                            text_color=C["muted"])
    app.lstatus.pack(side="right", padx=(20, 18), pady=10)


# ---------------------------------------------------------------------------
# VU Meter (medidor de nivel)
# ---------------------------------------------------------------------------

def build_vu_meter(app: "App", parent):
    """Construye el medidor de nivel de entrada (VU) con barra + historial."""
    vu = app._frame(parent, fg_color="transparent")
    vu.pack(side="left", padx=(0, 14), pady=12)

    vu_row1 = app._frame(vu, fg_color="transparent")
    vu_row1.pack(side="top", fill="x")
    app._lbl(vu_row1, "VU", font=(app.FB, 12)).pack(side="left", padx=(0, 6))
    if CTK:
        app.vu_bar = ctk.CTkProgressBar(vu_row1, width=170, height=10,
                                          corner_radius=5, fg_color=C["button"],
                                          progress_color=C["accent"])
        app.vu_bar.set(0)
        app._gold_bars.append(app.vu_bar)
    else:
        app.vu_bar = tk.ttk.Progressbar(vu_row1, mode="determinate",
                                         length=150, maximum=100)
        app.vu_bar['value'] = 0
    app.vu_bar.pack(side="left", padx=(0, 8))
    app.vu_lbl = app._lbl(vu_row1, "-inf dB", font=(app.FB, 10),
                           text_color=C["muted"])
    app.vu_lbl.pack(side="left")
    app.vu_warn = app._lbl(vu_row1, "", font=(app.FB, 10), text_color=C["warn"])
    app.vu_warn.pack(side="left", padx=(8, 0))

    # Historial + sensibilidad
    vu_row2 = app._frame(vu, fg_color="transparent")
    vu_row2.pack(side="top", fill="x", pady=(4, 0))
    app.vu_hist = tk.Canvas(vu_row2, width=160, height=24, bg=C["card"],
                             highlightthickness=1, highlightbackground=C["border"])
    app.vu_hist.pack(side="left", padx=(0, 6))
    app._lbl(vu_row2, "Sens:", font=(app.FB, 9), text_color=C["muted"]).pack(
        side="left", padx=(0, 4))
    if CTK:
        app.vu_sens_slider = ctk.CTkSlider(vu_row2, from_=0.05, to=0.60,
                                             number_of_steps=11,
                                             command=app._vu_sens_changed,
                                             width=110, height=16,
                                             progress_color=C["accent"],
                                             button_color=C["accent"])
    else:
        app.vu_sens_slider = tk.ttk.Scale(vu_row2, from_=0.05, to=0.60,
                                            orient="horizontal",
                                            command=app._vu_sens_changed,
                                            length=110)
    app.vu_sens_slider.set(app.vu_sens)
    app.vu_sens_slider.pack(side="left", padx=(0, 6))
    app.vu_sens_val = app._lbl(vu_row2, f"{app.vu_sens:.2f}", font=(app.FB, 9),
                                 text_color=C["muted"])
    app.vu_sens_val.pack(side="left")


# ---------------------------------------------------------------------------
# Barra de configuracion (perfil, motor, modelo, idioma)
# ---------------------------------------------------------------------------

def build_config_bar(app: "App", parent):
    """Construye la barra de configuracion: perfil, motor, modelo, idioma, VAD."""
    cfg = app._frame(parent, fg_color=C["card"])
    cfg.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))
    app.cfg_frame = cfg

    # Resumen de config (visible en Modo Guiado)
    cfg_sum = app._frame(parent, fg_color=C["card"])
    cfg_sum.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 4))
    app.cfg_sum_frame = cfg_sum
    app.lcfg_sum = app._lbl(cfg_sum, "", font=(app.FB, 11), text_color=C["muted"])
    app.lcfg_sum.pack(anchor="w", padx=18, pady=3)

    # Perfil
    app._lbl(cfg, "Perfil:", font=(app.FB, 12)).pack(side="left", padx=(18, 6), pady=12)
    app.profile_var = ctk.StringVar(value=app.config.get("audio_profile", "Clase Universitaria"))
    if CTK:
        app.cmb_profile = ctk.CTkOptionMenu(
            cfg, values=list(AudioPipeline.PROFILES.keys()),
            variable=app.profile_var, width=180, command=app._chprofile,
            font=(app.FB, 11))
    else:
        app.cmb_profile = tk.OptionMenu(cfg, app.profile_var,
                                         *AudioPipeline.PROFILES.keys(),
                                         command=app._chprofile)
    app.cmb_profile.pack(side="left", padx=(0, 20), pady=12)

    # Motor
    app._lbl(cfg, "Motor:", font=(app.FB, 12)).pack(side="left", padx=(0, 6), pady=12)
    app.mode_var = ctk.StringVar(value=app.config.get("transcription_mode", "local"))
    if CTK:
        for val, lbl in (("local", "Local"), ("cloud", "Cloud")):
            rb = ctk.CTkRadioButton(cfg, text=lbl, variable=app.mode_var, value=val,
                                     command=app._chmode, font=(app.FB, 11),
                                     text_color=C["text"])
            rb.pack(side="left", padx=(0, 14), pady=12)
            app._themeable.append(("label", rb, "text"))
    else:
        tk.OptionMenu(cfg, app.mode_var, "local", "cloud",
                       command=app._chmode).pack(side="left", padx=(0, 20), pady=12)

    # Modelo
    app._lbl(cfg, "Modelo:", font=(app.FB, 12)).pack(side="left", padx=(0, 6), pady=12)
    app.model_var = ctk.StringVar(value=app.config.get("local_model", "base"))
    if CTK:
        app.cmb_model = ctk.CTkOptionMenu(cfg, values=["tiny", "base", "small"],
                                            variable=app.model_var, width=90,
                                            command=app._chlocalmodel, font=(app.FB, 11))
    else:
        app.cmb_model = tk.OptionMenu(cfg, app.model_var, "tiny", "base", "small",
                                       command=app._chlocalmodel)
    app.cmb_model.pack(side="left", padx=(0, 20), pady=12)

    # Idioma
    app._lbl(cfg, "Idioma:", font=(app.FB, 12)).pack(side="left", padx=(0, 6), pady=12)
    app.lang_var = ctk.StringVar(value=app.config.get("whisper_language", "auto"))
    _langs = ["auto", "es", "en", "pt", "fr", "de", "it"]
    if CTK:
        app.cmb_lang = ctk.CTkOptionMenu(cfg, values=_langs, variable=app.lang_var,
                                           width=82, command=app._chlang, font=(app.FB, 11))
    else:
        app.cmb_lang = tk.OptionMenu(cfg, app.lang_var, *_langs, command=app._chlang)
    app.cmb_lang.pack(side="left", padx=(0, 20), pady=12)

    # Switches: Rapido + VAD
    app.fast_var = ctk.BooleanVar(value=False)
    if CTK:
        ctk.CTkSwitch(cfg, text="Rapido", variable=app.fast_var,
                       font=(app.FB, 11)).pack(side="left", padx=(0, 15), pady=12)
    else:
        tk.Checkbutton(cfg, text="Rapido", variable=app.fast_var,
                        bg=C["card"], fg=C["text"]).pack(side="left", padx=(0, 15), pady=12)

    app.vad_var = ctk.BooleanVar(value=True)
    if CTK:
        ctk.CTkSwitch(cfg, text="VAD", variable=app.vad_var, font=(app.FB, 11),
                       progress_color=C["ok"]).pack(side="left", padx=(0, 15), pady=12)
    else:
        tk.Checkbutton(cfg, text="VAD", variable=app.vad_var,
                        bg=C["card"], fg=C["text"]).pack(side="left", padx=(0, 15), pady=12)

    app.btheme = app._btn(cfg, "Claro", app._theme, width=90, height=32)
    app.btheme.pack(side="left", pady=12)


# ---------------------------------------------------------------------------
# Barra de progreso
# ---------------------------------------------------------------------------

def build_progress(app: "App", parent):
    """Construye la barra de progreso y etiqueta de estado."""
    pr = app._frame(parent, fg_color=C["card"])
    pr.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 10))
    app.lprog = app._lbl(pr, "", font=(app.FB, 11), text_color=C["muted"])
    app.lprog.pack(anchor="w", padx=18, pady=(12, 4))
    if CTK:
        app.pbar = ctk.CTkProgressBar(pr, height=12, corner_radius=6,
                                        progress_color=C["accent"],
                                        fg_color=C["button"])
        app.pbar.set(0)
        app._gold_bars.append(app.pbar)
    else:
        app.pbar = tk.ttk.Progressbar(pr, mode="determinate")
        app.pbar['value'] = 0
    app.pbar.pack(fill="x", padx=18, pady=(0, 14))


# ---------------------------------------------------------------------------
# Waveform (grafico de onda)
# ---------------------------------------------------------------------------

def build_waveform(app: "App", parent):
    """Construye el grafico de onda (matplotlib) o placeholder."""
    vz = app._frame(parent, fg_color=C["card"])
    vz.grid(row=5, column=0, sticky="nsew", padx=22, pady=(0, 6))

    if MPL:
        app.fig = Figure(figsize=(8, 0.6 if getattr(app, "_compact", False) else 1.5),
                          dpi=100, facecolor=C["card"])
        app.ax = app.fig.add_subplot(111)
        app.ax.set_facecolor(C["card"])
        app.ax.tick_params(colors=C["muted"], labelsize=8)
        for sp in app.ax.spines.values():
            sp.set_color(C["border"])
        app.ax.set_ylim(-0.5, 0.5)
        app.ax.set_xlim(0, VISUAL_SAMPLES)
        app.ax.set_xticks([])
        app.line, = app.ax.plot([], [], color=C["accent"], linewidth=1.8)
        app.canvas = FigureCanvasTkAgg(app.fig, master=vz)
        app.canvas.draw()
        app.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=6)
    else:
        app._lbl(vz, "Instala matplotlib: pip install matplotlib",
                  text_color=C["warn"]).pack(pady=35)


# ---------------------------------------------------------------------------
# Adaptacion Inteligente (botones de plantilla + area de texto)
# ---------------------------------------------------------------------------

def build_adapt(app: "App", parent):
    """Construye la seccion de Adaptacion Inteligente."""
    adapt = app._frame(parent, fg_color=C["card"], border_width=1,
                        border_color=C["gemini"])
    adapt.grid(row=6, column=0, sticky="nsew", padx=22, pady=(0, 18))
    adapt.grid_rowconfigure(2, weight=1)
    adapt.grid_columnconfigure(0, weight=1)

    ah = app._frame(adapt, fg_color="transparent")
    ah.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
    app._lbl(ah, "Adaptacion Inteligente", font=(app.FH, 14, "bold"),
             text_color=C["gemini"]).pack(side="left")
    app.ladapt = app._lbl(ah, "Sin API Key", font=(app.FB, 11),
                           text_color=C["warn"])
    app.ladapt.pack(side="right")

    app._lbl(adapt, "Selecciona que quieres generar a partir de la transcripcion:",
              font=(app.FB, 11), text_color=C["muted"]).grid(
        row=1, column=0, sticky="w", padx=18, pady=(0, 8))

    btn_frame = app._frame(adapt, fg_color="transparent")
    btn_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))

    app.adapt_buttons = {}
    app.adapt_extra = []
    templates = list(GeminiAdaptationEngine.TEMPLATES.items())
    for idx, (name, info) in enumerate(templates):
        row, col = divmod(idx, 4)
        b = app._btn(btn_frame, f"{info['icon']} {name}",
                      lambda n=name: app._adapt(n),
                      width=170, height=38, state="disabled",
                      fg_color=C["button"], hover_color=C["border"])
        b.grid(row=row, column=col, padx=6, pady=6)
        app.adapt_buttons[name] = b
        if idx > 0:
            app.adapt_extra.append(b)

    app.adapt_info = app._lbl(adapt, "", font=(app.FB, 10), text_color=C["muted"])
    app.adapt_info.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 4))

    if CTK:
        app.adapt_txt = ctk.CTkTextbox(adapt, font=("Consolas", 11), wrap="word",
                                         corner_radius=8, fg_color=C["bg"],
                                         text_color=C["text"], height=140)
    else:
        app.adapt_txt = scrolledtext.ScrolledText(adapt, wrap=tk.WORD,
                                                    font=("Consolas", 11),
                                                    bg=C["bg"], fg=C["text"],
                                                    height=7)
    app.adapt_txt.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 14))
    app.adapt_txt.configure(state="disabled")

    app.bsave_adapt = app._btn(adapt, "Guardar Adaptacion", app._save_adaptation,
                                width=180, height=36, state="disabled")
    app.bsave_adapt.grid(row=5, column=0, sticky="w", padx=18, pady=(0, 12))


# ---------------------------------------------------------------------------
# Editor de Transcripcion
# ---------------------------------------------------------------------------

def build_transcription(app: "App", parent):
    """Construye el editor de transcripcion con gutter de lineas."""
    tr = app._frame(parent, fg_color=C["card"], border_width=1,
                     border_color=C["border"])
    tr.grid(row=7, column=0, sticky="nsew", padx=22, pady=(0, 5))
    tr.grid_rowconfigure(1, weight=1)
    tr.grid_columnconfigure(0, weight=1)

    th = app._frame(tr, fg_color="transparent")
    th.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
    app._lbl(th, "Transcripcion", font=(app.FH, 15, "bold"),
             text_color=C["text"]).pack(side="left")
    app.lbadge = app._lbl(th, "Revisado por IA", font=(app.FB, 10, "bold"),
                           text_color=C["ok"])
    app.lbadge.pack(side="right", padx=(0, 14))
    app.lbadge.pack_forget()
    app._btn(th, "Copiar", app._copy_trans, width=92, height=28,
             font=(app.FB, 10), fg_color=C["button"],
             hover_color=C["border"]).pack(side="right", padx=(0, 14))
    app.lmodel = app._lbl(th, "Cargando...", font=(app.FB, 11),
                           text_color=C["warn"])
    app.lmodel.pack(side="right")

    tbox = app._frame(tr, fg_color=C["bg"], border_width=1,
                       border_color=C["border"])
    tbox.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))
    tbox.grid_rowconfigure(0, weight=1)
    tbox.grid_columnconfigure(1, weight=1)

    # Gutter
    app.txt_gutter = tk.Text(tbox, width=4, wrap="none", state="disabled",
                              height=5 if getattr(app, "_compact", False) else 8,
                              bg=C["card"], fg=C["muted"], font=(app.FM, 11),
                              padx=6, pady=8, relief="flat", borderwidth=0,
                              highlightthickness=0, takefocus=0)
    app.txt_gutter.grid(row=0, column=0, sticky="nsew")

    # Area de texto
    app.txt = tk.Text(tbox, wrap="word", state="disabled",
                       height=5 if getattr(app, "_compact", False) else 8,
                       bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                       font=(app.FM, 11), padx=12, pady=8,
                       relief="flat", borderwidth=0, highlightthickness=0)
    app.txt.grid(row=0, column=1, sticky="nsew")
    app.txt.configure(yscrollcommand=app._txt_yscroll)
    app.txt.tag_configure("live", foreground=C["accent"])
    app.txt.tag_configure("head", foreground=C["accent"], font=(app.FM, 11, "bold"))
    app.vsb = tk.Scrollbar(tbox, orient="vertical", command=app.txt.yview,
                             bg=C["border"], troughcolor=C["bg"], relief="flat")
    app.vsb.grid(row=0, column=2, sticky="ns")
    app._fill_gutter()


# ---------------------------------------------------------------------------
# Footer (barra inferior)
# ---------------------------------------------------------------------------

def build_footer(app: "App", parent):
    """Construye la barra inferior: ruta, atajos, mic, reloj."""
    ft = app._frame(parent, fg_color=C["card"], border_width=1,
                     border_color=C["border"])
    ft.grid(row=8, column=0, sticky="ew", padx=22, pady=(0, 5))
    ftl = app._frame(ft, fg_color="transparent")
    ftl.pack(side="left")
    app._lbl(ftl, f"{OUTPUT_DIR}", font=(app.FB, 10),
             text_color=C["muted"]).pack(side="left")
    app._lbl(ft, "Espacio  -  Ctrl+R grabar  -  Ctrl+S guardar  -  Ctrl+E exportar  -  F1 ayuda",
              font=(app.FB, 10), text_color=C["muted"]).pack(side="right", padx=(0, 18))
    app._btn(ftl, "Abrir carpeta", app._open_output_dir, width=130, height=28,
             font=(app.FB, 10)).pack(side="left", padx=(12, 0))
    app._btn(ftl, "Probar microfono", app._test_mic, width=170, height=28,
             font=(app.FB, 10), fg_color=C["accent"],
             hover_color=C["accent_hover"]).pack(side="left", padx=(8, 0))
    app._btn(ftl, "Optimizar microfono", app._open_mic_opt, width=195, height=28,
             font=(app.FB, 10), fg_color=C["ok"],
             hover_color=C["ok"]).pack(side="left", padx=(8, 0))
    app.ltime = app._lbl(ft, "", font=(app.FB, 10), text_color=C["muted"])
    app.ltime.pack(side="right")
