#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AudioClass v9.1 — Edición Académica Profesional
================================================
Para personas que no saben de terminales ni programación.
Todo se controla con botones. Todo se guarda solo.

Novedades v9.1:
• Prompt académico de élite: filtro cognitivo con identificación de orador principal,
  extracción de tesis, pilares, evidencia dura y registro de filtrado
• Transcripción condicionada para priorizar voz del docente
• Pipeline de audio profesional con 4 perfiles preconfigurados
• Modo Fácil: Grabar → Procesar → Transcribir → Analizar (1 botón)
• Motor Local (Tiny/Base/Small) + Cloud Colab (Medium/Large-v3)
• Adaptación Inteligente vía Gemini API (Google AI Studio)
• Segmentación automática para textos largos (sin caídas de servidor)

Para compilar:
    pyinstaller AudioClass.spec --clean --noconfirm
"""

import os, sys, threading, queue, time, warnings, shutil, subprocess, traceback, json, re, textwrap, tempfile, hashlib, base64
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path

# ─── EXE SIN CONSOLA: red de seguridad para stdout/stderr ──────────────────
# PyInstaller con console=False (y pythonw) dejan sys.stdout/sys.stderr en
# None: cualquier libreria que escriba a stdout (p. ej. tqdm dentro de whisper)
# reventaria con AttributeError ('NoneType' object has no attribute 'write').
# El motor ya llama a whisper con verbose=None para no escribir nada, pero este
# sumidero nulo protege de cualquier otra escritura accidental.
class _NullWriter:
    def write(self, *a, **k):
        return 0
    def flush(self, *a, **k):
        pass
    def writelines(self, *a, **k):
        pass
    def isatty(self):
        return False
if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

# ─── LOGGING ROTATIVO ────────────────────────────────────────────────────────
# Todo error no critico se registra en ~/AudioClass_Recordings/logs/audioclass.log
# (con rotacion a 2 MB x 3 copias) para poder diagnosticar fallos del usuario
# sin depender de que vea la pantalla. Las excepciones se registran con su
# traceback completo; la UI muestra solo un mensaje breve.
# Logging rotativo centralizado en audioclass_core.py (mejora #9)
from audioclass_core import LOG_DIR, _setup_logger, log_exc, log_info

import numpy as np
import sounddevice as sd
from scipy import signal
from scipy.io import wavfile

# ─── UI ─────────────────────────────────────────────────────────────────────
import tkinter as tk
try:
    import customtkinter as ctk
    CTK = True
    ctk.set_appearance_mode("dark")
    _CTK_THEME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "audioclass_theme.json")
    try:
        ctk.set_default_color_theme(_CTK_THEME if os.path.exists(_CTK_THEME) else "gold")
    except Exception:
        ctk.set_default_color_theme("gold")
    from tkinter import filedialog
except ImportError:
    import tkinter as ctk
    from tkinter import ttk, scrolledtext, messagebox, filedialog
    CTK = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL = True
except ImportError:
    MPL = False

warnings.filterwarnings("ignore")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN GLOBAL Y PERSISTENTE
# ═══════════════════════════════════════════════════════════════════════════════
APP_NAME = "AudioClass"
APP_VER = "9.1 Académica"
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.float32
CHUNK_DUR = 0.1   # 100 ms por bloque: reduce desbordamientos (estatica/cortes)
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DUR)
VISUAL_SAMPLES = int(SAMPLE_RATE * 2.0)
# Pre-check de microfono antes de grabar: mide ~1.5 s de entrada y, si el p90
# del RMS queda bajo el umbral (calibrado con optimizar_mic.py: SILENCIO < 0.005,
# DEBIL < 0.03, voz real >= 0.03), muestra una advertencia visible pidiendo
# confirmacion antes de empezar (evita clases grabadas casi en silencio).
MIC_PROBE_SECONDS = 1.5
MIC_PROBE_P90_MIN = 0.01

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "AudioClass_Recordings")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _sweep_stale_temps(max_age=3600):
    """Borra temporales de grabacion (ac_rec_*.raw) abandonados por cierres
    abruptos, apagados o bloqueos. Solo los mas viejos que max_age segundos:
    uno reciente puede pertenecer a una grabacion en curso."""
    try:
        now = time.time()
        tdir = tempfile.gettempdir()
        for fn in os.listdir(tdir):
            if fn.startswith("ac_rec_") and fn.endswith(".raw"):
                p = os.path.join(tdir, fn)
                try:
                    if now - os.path.getmtime(p) > max_age:
                        os.remove(p)
                except OSError:
                    pass
    except Exception:
        pass


CONFIG_PATH = os.path.join(OUTPUT_DIR, "audioclass_config.json")

# ── Sistema de diseño (escala azul-gris-blanco-negro, WCAG AA) ─────────────
# El acento es AZUL; fondos y superficies en escala de grises/azules pizarra;
# el ROJO queda reservado para GRABACIÓN y acciones de peligro. Cada color se
# eligió para cumplir WCAG AA: texto normal >= 4.5:1 sobre bg/card, y el texto
# de los botones se calcula dinámicamente (_btn_text_color) según la
# luminancia del fondo (oscuro sobre fondos claros, blanco sobre oscuros).
PALETTES = {
    "dark": {
        "bg": "#0F172A", "card": "#1E293B", "accent": "#60A5FA",
        "text": "#E2E8F0", "muted": "#94A3B8", "ok": "#22D3EE",
        "warn": "#F59E0B", "err": "#F07171", "border": "#64748B",
        "cloud": "#60A5FA", "gemini": "#60A5FA", "mic": "#F07171",
        "easy": "#22D3EE", "button": "#334155", "academic": "#60A5FA",
        "header": "#0F172A", "head_text": "#E2E8F0", "accent_hover": "#3B82F6"
    },
    "light": {
        "bg": "#F1F5F9", "card": "#FFFFFF", "accent": "#2563EB",
        "text": "#000000", "muted": "#475569", "ok": "#0F766E",
        "warn": "#92400E", "err": "#B91C1C", "border": "#7C8CA0",
        "cloud": "#1D4ED8", "gemini": "#2563EB", "mic": "#B91C1C",
        "easy": "#0F766E", "button": "#E2E8F0", "academic": "#2563EB",
        "header": "#1E293B", "head_text": "#F1F5F9", "accent_hover": "#1D4ED8"
    },
}


def _relative_luminance(hexc):
    """Luminancia relativa WCAG de un color hex."""
    hexc = str(hexc).lstrip("#")
    vals = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(vals[0]) + 0.7152 * lin(vals[1]) + 0.0722 * lin(vals[2])


def _btn_text_color(bg):
    """Texto de boton con el MAYOR contraste WCAG posible sobre el fondo dado:
    negro o blanco, el que gane. Asi ningun boton queda con texto ilegible
    (p. ej. azules medios donde el umbral fijo elegia el color equivocado)."""
    try:
        l = _relative_luminance(bg)
        # Contraste relativo de negro y de blanco contra el fondo
        c_black = (l + 0.05) / 0.05
        c_white = 1.05 / (l + 0.05)
        return "#000000" if c_black >= c_white else "#FFFFFF"
    except Exception:
        return "#FFFFFF"
C = PALETTES["dark"].copy()

# ── Tipografía ────────────────────────────────────────────────────────────────
# Merriweather / Inter / Source Code Pro si están instalados; si no, caen a la
# serif / sans / mono de Windows. Las fuentes DejaVu empaquetadas (assets/) se
# registran en _load_bundled_fonts para los acentos unicode.
def _resolve_fonts():
    import tkinter.font as tkfont
    try:
        fams = set(tkfont.families())
    except Exception:
        fams = set()
    head = next((f for f in ("Merriweather", "Georgia", "Cambria", "Times New Roman") if f in fams), "Segoe UI")
    body = next((f for f in ("Inter", "Segoe UI", "Tahoma") if f in fams), "Segoe UI")
    mono = next((f for f in ("Source Code Pro", "Consolas", "Courier New") if f in fams), "Consolas")
    return head, body, mono

def _load_bundled_fonts():
    """Registra las fuentes DejaVu empaquetadas (assets/) para Tk/CTk."""
    try:
        if not CTK:
            return
        base = os.path.dirname(os.path.abspath(__file__))
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
        for f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
            p = os.path.join(base, "assets", f)
            if os.path.exists(p):
                ctk.FontManager.load_font(p)
    except Exception:
        pass

DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "colab_url": "",
    "colab_key": "audioclass",
    "google_creds_path": "",
    "audio_profile": "Clase Universitaria",
    "transcription_mode": "local",
    "local_model": "base",
    # Idioma de whisper: "auto" = detecta el idioma del audio; si no, un
    # codigo ISO (es, en, pt, fr, ...) que se fuerza.
    "whisper_language": "auto",
    "cloud_model": "large-v3",
    "gemini_model": "flash",
    "adapt_provider": "gemini",
    "openai_api_key": "",
    "openai_model": "mini",
    "modo_facil": False,
    "modo_guiado": True,
    "auto_adaptar": False,
    "adaptacion_default": "Análisis Académico Profundo",
    "theme": "dark",
    "vu_sensitivity": 0.25,
    "first_run": True,
    # Privacidad: el analisis con IA ENVIA el texto de la transcripcion a
    # servidores de Google/OpenAI. Sin consentimiento explicito (ia_consent),
    # la app pide permiso antes del primer uso y nunca envia nada.
    "ia_consent": False,
    "rec_consent_ack": False
}

# ─── CIFRADO DE SECRETOS (DPAPI en Windows) ──────────────────────────────────
# La API key de Gemini y la clave de Colab se guardan cifradas con DPAPI
# (CryptProtectData, nativo de Windows, sin dependencias). El blob queda ligado
# al usuario de Windows: solo la misma sesion puede descifrarlo. En sistemas no
# Windows (o si DPAPI falla) se usa base64 como ofuscacion minimo; los valores
# legados en texto plano se siguen leyendo y se re-guardan cifrados.

def _encrypt_secret(secret):
    """Cifra un secreto. Devuelve string con prefijo 'dpapi:' o 'b64:'."""
    if not secret:
        return ""
    s = str(secret)
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD),
                            ("pbData", ctypes.POINTER(ctypes.c_char))]

            def _blob(data):
                buf = ctypes.create_string_buffer(data)
                return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

            crypt32 = ctypes.windll.crypt32
            crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR,
                                                 ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
                                                 ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
            crypt32.CryptProtectData.restype = wintypes.BOOL
            try:
                from ctypes import byref
                inb = _blob(s.encode("utf-8"))
                outb = DATA_BLOB()
                if crypt32.CryptProtectData(byref(inb), u"audioclass", None, None, None, 0, byref(outb)):
                    raw = ctypes.string_at(outb.pbData, outb.cbData)
                    # LocalFree es de kernel32, no de crypt32
                    ctypes.windll.kernel32.LocalFree(outb.pbData)
                    return "dpapi:" + base64.b64encode(raw).decode("ascii")
            except Exception:
                pass
        except Exception:
            pass
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def _decrypt_secret(value):
    """Descifra un secreto cifrado con _encrypt_secret. Valores legados en
    texto plano se devuelven tal cual (y luego se re-guardan cifrados)."""
    if not value:
        return ""
    v = str(value)
    if v.startswith("b64:"):
        try:
            return base64.b64decode(v[4:]).decode("utf-8")
        except Exception:
            return ""
    if v.startswith("dpapi:") and os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD),
                            ("pbData", ctypes.POINTER(ctypes.c_char))]

            crypt32 = ctypes.windll.crypt32
            crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPCWSTR),
                                                   ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
                                                   ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)]
            crypt32.CryptUnprotectData.restype = wintypes.BOOL
            try:
                from ctypes import byref
                raw = base64.b64decode(v[6:])
                buf = ctypes.create_string_buffer(raw)
                inb = DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
                outb = DATA_BLOB()
                if crypt32.CryptUnprotectData(byref(inb), None, None, None, None, 0, byref(outb)):
                    out = ctypes.string_at(outb.pbData, outb.cbData).decode("utf-8")
                    ctypes.windll.kernel32.LocalFree(outb.pbData)
                    return out
            except Exception:
                return ""
        except Exception:
            return ""
    return v


_SECRET_FIELDS = ("gemini_api_key", "openai_api_key", "colab_key")

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            for k in _SECRET_FIELDS:
                if k in cfg and cfg[k]:
                    cfg[k] = _decrypt_secret(cfg[k])
            return cfg
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    to_save = dict(cfg)
    for k in _SECRET_FIELDS:
        if k in to_save and to_save[k]:
            to_save[k] = _encrypt_secret(to_save[k])
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════════════════════
# NUCLEO DE PROCESAMIENTO — extraido a audioclass_core.py (mejora #9)
# Se importa aqui para que toda la UI y los tests sigan usando los mismos
# nombres (AudioPipeline, LocalWhisperEngine, ...) sin cambios.
# ═══════════════════════════════════════════════════════════════════════════════
from audioclass_core import (AudioPipeline, LocalWhisperEngine,
                             CloudColabEngine, GeminiAdaptationEngine,
                             OpenAIAdaptationEngine, build_adaptation_engine,
                             GoogleDocsExporter)
# ═══════════════════════════════════════════════════════════════════════════════
# UI PRINCIPAL — AudioClass v9.1 (continuación)
# ═══════════════════════════════════════════════════════════════════════════════

# Simbolos tipograficos comunes -> sustituto ASCII. Solo se aplican como
# compatibilidad cuando NO hay fuente Unicode (con DejaVu no hacen falta).
_PDF_FALLBACK_CHARS = {
    "—": "-", "–": "-", "…": "...", "•": "-", "→": "->",
    "├": "|", "└": "`", "“": '"', "”": '"', "‘": "'", "’": "'",
}

_GDOCS_IMPORTABLE = None


def _gdocs_importable():
    """True si google-auth-oauthlib + googleapiclient estan instalados
    (necesarios para exportar a Google Docs). En el exe de distribucion NO
    viajan por defecto: el boton se desactiva con mensaje claro en lugar de
    fallar al pulsarlo. Lazy + cache para no pagar el import al arrancar."""
    global _GDOCS_IMPORTABLE
    if _GDOCS_IMPORTABLE is None:
        try:
            import google_auth_oauthlib  # noqa: F401
            import googleapiclient        # noqa: F401
            import google.oauth2.credentials  # noqa: F401
            _GDOCS_IMPORTABLE = True
        except Exception:
            _GDOCS_IMPORTABLE = False
    return _GDOCS_IMPORTABLE


class App(ctk.CTk if CTK else ctk.Tk):
    def __init__(self):
        try:
            if CTK:
                super().__init__()
            else:
                ctk.Tk.__init__(self)
                self.configure(bg=C["bg"])

            self.title(f"{APP_NAME} v{APP_VER}")

            # Sistema de diseño: fuentes (serif/sans/mono) y tema persistente
            self.FH, self.FB, self.FM = _resolve_fonts()
            _load_bundled_fonts()

            self.config = load_config()
            self.dark = (self.config.get("theme", "dark") == "dark")
            C.clear(); C.update(PALETTES["dark" if self.dark else "light"])
            if CTK: ctk.set_appearance_mode("dark" if self.dark else "light")

            # Ventana adaptativa: cabe en pantallas pequenas (1366x768) y
            # aprovecha las grandes. Antes fijaba 1450x1050 y en pantallas
            # menores el editor de transcripcion quedaba recortado fuera de
            # vista (el grid no comprime por debajo del tamano natural).
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            # h = sh - 70: descuenta la barra de tareas (~40px) y la de titulo
            # (~31px) para que la ventana NUNCA quede parcialmente fuera de
            # pantalla (antes el borde inferior quedaba negro en la captura).
            w = min(1450, max(900, sw))
            h = min(1050, max(600, sh - 70))
            # Modo compacto para pantallas pequenas: el contenido natural del
            # grid (~950px) no cabe en 1366x768, asi que se ocultan piezas de
            # cromo (banner de siguiente paso, subtitulo de Modo Facil, pie de
            # salida) y se encogen waveform y editor para que la transcripcion
            # quede visible.
            self._compact = bool(sh < 950)
            if self.config.get("first_run", True):
                # Asistente de bienvenida: ventana compacta que quepa en
                # portatiles (la principal se restaura al terminar).
                self.geometry("1120x720")
                self.minsize(900, 560)
            else:
                # Centrar en la pantalla (y con margen para la barra de tareas).
                px = max(0, (sw - w) // 2)
                py = max(0, (sh - 40 - h) // 2)
                self.geometry(f"{w}x{h}+{px}+{py}")
                self.minsize(1000, 620)
            if CTK:
                # El root de CTk usa por defecto el gris del tema; pintarlo con
                # la paleta activa para que el fondo nunca quede negro.
                try:
                    self.configure(fg_color=C["bg"])
                except Exception:
                    pass

            self.recording = False
            self._stop_done = False   # idempotencia de _stoprec (doble clic)
            self._proc_active = False # _procsave en curso (race con _close)
            self.buffer = []
            self.vizbuf = np.zeros(VISUAL_SAMPLES, dtype=np.float32)
            self.last_path = None
            self.last_text = ""
            self.last_segments = []
            self.last_model = "Whisper"
            self.cancel = False
            self.stop_ev = threading.Event()
            self.q = queue.Queue()
            # Estabilidad: limpiar temporales abandonados de sesiones previas
            _sweep_stale_temps()
            self.history = []
            self.sel = None
            self.compile_buffer = []
            self._themeable = []   # superficies registradas para re-mapear en _apply_palette
            self._gold_bars = []   # barras de progreso doradas (pbar, vu_bar)
            self._pulse_active = False
            self._pulse_after = None
            self._next_guide_step = 1
            self._transcribing = False
            self._trans_start = 0.0
            self._trans_msg = ""
            self._pending_trans = None
            self._pending_after = None
            self._last_trans_req = (False, False)   # ultima peticion (timestamps, auto_adapt) para Reintentar
            self._audio_overflows = 0
            self.vu_clips = 0
            self.vu_low = 0
            self.vu_rms_hist = []       # historial RMS para detectar estatica (audio sin voz)
            self.vu_static = False      # flag: se detecto nivel constante (estatica)
            self.vu_rms_hist_full = []  # historial RMS ultimos 10 s (125 lecturas) para mini-grafico
            self.vu_sens = float(self.config.get("vu_sensitivity", 0.25))  # umbral CV de sensibilidad

            self.local_engine = LocalWhisperEngine(
                self.config.get("local_model", "base"),
                self.config.get("whisper_language", "auto")
            )
            self.cloud_engine = CloudColabEngine(
                self.config.get("colab_url", ""),
                self.config.get("colab_key", "audioclass"),
                self.config.get("whisper_language", "auto")
            )
            self.adapt_engine = self._build_adapt_engine()
            self.docs_exporter = GoogleDocsExporter(
                self.config.get("google_creds_path", "")
            )

            self.pipeline = AudioPipeline(
                self.config.get("audio_profile", "Clase Universitaria"),
                fast_mode=False, use_vad=True
            )

            if self.config.get("first_run", True):
                self._show_wizard()
            else:
                self._build_main_ui()

            self._poll()
            self.protocol("WM_DELETE_WINDOW", self._close)

        except Exception as e:
            self._fatal(e)

    def _fatal(self, e):
        import tkinter.messagebox as mb
        mb.showerror("Error fatal", f"No se pudo iniciar AudioClass:\n\n{e}\n\n{traceback.format_exc()}")
        sys.exit(1)

    def _msg(self, kind, title, msg):
        import tkinter.messagebox as mb
        if kind == "error": mb.showerror(title, msg)
        elif kind == "warning": mb.showwarning(title, msg)
        else: mb.showinfo(title, msg)

    def _ask(self, t, m):
        import tkinter.messagebox as mb
        return mb.askyesno(t, m)

    def _btn(self, p, txt, cmd, **kw):
        d = {"font": (self.FB, 12), "corner_radius": 10, "height": 40}
        d.update(kw)
        no_theme = d.pop("no_theme", False)
        # Unificacion de tema: sin fg_color explicito, el boton usaba el azul
        # por defecto del tema CTk (fuera de paleta) y texto gray60 al estar
        # disabled (contraste ~2:1 sobre azul). Default = C["button"] de la
        # paleta y registro para re-tematizado claro/oscuro.
        if not d.get("fg_color"):
            d["fg_color"] = C["button"]
        if CTK:
            w = ctk.CTkButton(p, text=txt, command=cmd, **d)
            # Texto de contraste segun el fondo del boton (WCAG AA): oscuro
            # sobre fondos claros, blanco sobre fondos oscuros.
            fg = d.get("fg_color")
            if fg and fg != "transparent":
                try:
                    w.configure(text_color=_btn_text_color(fg),
                                text_color_disabled=C["muted"])
                except Exception:
                    pass
            # Registrar los botones para re-tematizarlos en el cambio
            # claro/oscuro (igual que _lbl/_frame). Los que usan colores
            # fijos (hover literales, estado dinamico) no se registran.
            if not no_theme:
                key = self._palette_key(fg)
                if key:
                    self._themeable.append(("btn", w, key))
            return w
        b = ctk.Button(p, text=txt, command=cmd, font=d.get("font"))
        if "state" in d: b.config(state=d["state"])
        if "fg_color" in d:
            b.config(bg=d["fg_color"], fg=_btn_text_color(d["fg_color"]))
        return b

    def _lbl(self, p, txt, **kw):
        # theme_key fuerza la clave de paleta cuando dos colores comparten hex
        # en un tema (p. ej. head_text == text en oscuro) y el remapeo claro/
        # oscuro iria a la clave equivocada.
        tkey = kw.pop("theme_key", None)
        if CTK:
            w = ctk.CTkLabel(p, text=txt, **kw)
            col = kw.get("text_color", C["text"])
            if col:
                key = tkey or self._palette_key(col)
                if key:
                    self._themeable.append(("label", w, key))
            return w
        w = ctk.Label(p, text=txt, font=kw.get("font", ("Segoe UI", 11)), bg=C["card"], fg=C["text"])
        self._themeable.append(("label", w, self._palette_key(C["text"])))
        return w

    def _entry(self, p, **kw):
        if CTK:
            return ctk.CTkEntry(p, **kw)
        return ctk.Entry(p, font=kw.get("font", ("Segoe UI", 11)), bg=C["card"], fg=C["text"], insertbackground=C["text"])

    def _palette_key(self, value, forced=None):
        """Convierte un color a su CLAVE de paleta activa (primera coincidencia).
        Registrar la clave (no el valor) hace el re-mapeo de tema inequívoco
        aunque dos claves compartan el mismo hex (p. ej. bg==header en oscuro).
        forced permite fijar la clave en casos ambiguos (theme_key="header")."""
        if forced:
            return forced
        if value in (None, "transparent", ""):
            return None
        cur = PALETTES["dark" if self.dark else "light"]
        for k, v in cur.items():
            if v == value:
                return k
        return None

    def _frame(self, p, **kw):
        if CTK:
            # Diseno: las tarjetas (frames con fondo) llevan un borde sutil
            # para separar visualmente secciones sin depender solo del color.
            tkey = kw.pop("theme_key", None)
            if kw.get("fg_color") not in (None, "transparent"):
                kw.setdefault("border_width", 1)
                kw.setdefault("border_color", C["border"])
            w = ctk.CTkFrame(p, corner_radius=12, **kw)
            fg = kw.get("fg_color")
            if fg not in (None, "transparent"):
                self._themeable.append(("frame", w, self._palette_key(fg, tkey)))
            return w
        w = ctk.Frame(p, bg=C["card"])
        self._themeable.append(("frame", w, self._palette_key(C["card"])))
        return w

    def _show_wizard(self):
        # Contenedor del asistente: cuerpo desplazable (fila 0) + barra de
        # acciones SIEMPRE visible (fila 1). La barra se crea primero y va
        # fuera del scroll: antes, en pantallas no muy grandes, el boton
        # "Comenzar" quedaba fuera de la vista sin forma de llegar a el
        # (cuello de botella: no se podia continuar).
        self.wizard = ctk.CTkFrame(self, fg_color=C["bg"]) if CTK else ctk.Frame(self, bg=C["bg"])
        self.wizard.pack(fill="both", expand=True)
        self.wizard.grid_rowconfigure(0, weight=1)
        self.wizard.grid_columnconfigure(0, weight=1)

        _wparent = self.wizard
        bar = self._frame(_wparent, fg_color=C["card"], border_width=1, border_color=C["border"])
        bar.grid(row=1, column=0, sticky="ew")
        self._lbl(bar, "No te preocupes: todo esto se puede cambiar después en Configuración.",
                  font=("Segoe UI", 11), text_color=C["muted"]).pack(side="left", padx=(24, 12), pady=14)
        self._btn(bar, "🚀 Comenzar a usar AudioClass", self._finish_wizard,
                  width=320, height=48, font=("Segoe UI", 16, "bold"),
                  fg_color=C["accent"], hover_color=C["accent_hover"]).pack(side="right", padx=(12, 24), pady=10)

        # Cuerpo DESPLAZABLE (CTK: CTkScrollableFrame; fallback tk: Canvas+Scrollbar)
        if CTK:
            body = ctk.CTkScrollableFrame(_wparent, fg_color=C["bg"], corner_radius=0,
                                          scrollbar_button_color=C["border"])
            body.grid(row=0, column=0, sticky="nsew")
        else:
            from tkinter import Canvas, Scrollbar
            canvas = Canvas(_wparent, bg=C["bg"], highlightthickness=0)
            sbar = Scrollbar(_wparent, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=sbar.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            sbar.grid(row=0, column=1, sticky="ns")
            body = ctk.Frame(canvas, bg=C["bg"])
            body_id = canvas.create_window((0, 0), window=body, anchor="nw")

            def _on_body_conf(_e):
                canvas.configure(scrollregion=canvas.bbox("all"))
            body.bind("<Configure>", _on_body_conf)

            def _on_canvas_conf(e):
                canvas.itemconfigure(body_id, width=e.width)
            canvas.bind("<Configure>", _on_canvas_conf)
            canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
            body.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        body.grid_columnconfigure(0, weight=1)

        self._lbl(body, "🎓 ¡Bienvenido a AudioClass!",
                  font=("Segoe UI", 30, "bold"), text_color=C["accent"]).pack(pady=(34, 8))
        self._lbl(body, "Configuración rápida — 2 minutos y listo",
                  font=("Segoe UI", 14), text_color=C["muted"]).pack(pady=(0, 22))

        f0 = self._frame(body, fg_color=C["card"])
        f0.pack(fill="x", padx=100, pady=10)
        self._lbl(f0, "1. ¿Cómo quieres empezar?",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        self._lbl(f0, "La vista simple oculta las opciones avanzadas y muestra solo lo esencial.",
                  font=("Segoe UI", 11), text_color=C["muted"]).pack(anchor="w", padx=20, pady=(0, 10))

        self.wiz_level = ctk.StringVar(value="nuevo")
        if CTK:
            ctk.CTkRadioButton(f0, text="🧭 Soy nuevo — vista simple (recomendado)",
                               variable=self.wiz_level, value="nuevo",
                               font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=5)
            ctk.CTkRadioButton(f0, text="⚙️ Soy avanzado — quiero ver todas las opciones",
                               variable=self.wiz_level, value="avanzado",
                               font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=5)
        else:
            ctk.Radiobutton(f0, text="Soy nuevo - vista simple (recomendado)",
                           variable=self.wiz_level, value="nuevo",
                           bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)
            ctk.Radiobutton(f0, text="Soy avanzado - quiero ver todas las opciones",
                           variable=self.wiz_level, value="avanzado",
                           bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)

        f1 = self._frame(body, fg_color=C["card"])
        f1.pack(fill="x", padx=100, pady=10)
        self._lbl(f1, "2. ¿Dónde vas a grabar tus clases?", 
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        self._lbl(f1, "Elige el que mejor se parezca a tu sala. AudioClass ajusta el audio solo.",
                  font=("Segoe UI", 11), text_color=C["muted"]).pack(anchor="w", padx=20, pady=(0, 10))

        self.wiz_profile = ctk.StringVar(value="Clase Universitaria")
        for name, info in AudioPipeline.PROFILES.items():
            if CTK:
                ctk.CTkRadioButton(f1, text=f"{name} — {info['desc']}", 
                                   variable=self.wiz_profile, value=name,
                                   font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=5)
            else:
                ctk.Radiobutton(f1, text=f"{name} — {info['desc']}", 
                               variable=self.wiz_profile, value=name,
                               bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)

        f2 = self._frame(body, fg_color=C["card"])
        f2.pack(fill="x", padx=100, pady=10)
        self._lbl(f2, "3. ¿Tienes una API Key de IA? (opcional, pero recomendada)",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        self._lbl(f2, "Sirve para analizar tus clases con IA (resúmenes, guías, exámenes). Gemini es gratis: aistudio.google.com/app/apikey. También puedes usar OpenAI (GPT): añade su clave luego en Configuración.",
                  font=("Segoe UI", 11), text_color=C["muted"]).pack(anchor="w", padx=20, pady=(0, 10))
        self.wiz_gemini = self._entry(f2, width=500, font=("Segoe UI", 12), placeholder_text="Pega aquí tu API Key de Gemini (puedes dejarlo vacío y añadirla luego)...")
        self.wiz_gemini.pack(anchor="w", padx=20, pady=(0, 15))
        try:
            # Pulsar Enter en el campo de la API Key tambien continua
            self.wiz_gemini.bind("<Return>", lambda _e: self._finish_wizard())
        except Exception:
            pass

        f3 = self._frame(body, fg_color=C["card"])
        f3.pack(fill="x", padx=100, pady=10)
        self._lbl(f3, "4. ¿Cómo quieres transcribir?",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        self.wiz_mode = ctk.StringVar(value="local")
        if CTK:
            ctk.CTkRadioButton(f3, text="🖥️ En mi computadora (rápido y sin internet)", 
                               variable=self.wiz_mode, value="local",
                               font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=5)
            ctk.CTkRadioButton(f3, text="☁️ En Google Colab (mayor precisión, necesita internet)", 
                               variable=self.wiz_mode, value="cloud",
                               font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=5)
        else:
            ctk.Radiobutton(f3, text="En mi computadora", variable=self.wiz_mode, value="local",
                           bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)
            ctk.Radiobutton(f3, text="En Google Colab", variable=self.wiz_mode, value="cloud",
                           bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)

        f4 = self._frame(body, fg_color=C["card"])
        f4.pack(fill="x", padx=100, pady=10)
        self._lbl(f4, "5. Privacidad y consentimiento",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        self._lbl(f4, "🔒 Tus grabaciones y transcripciones se procesan en TU equipo y se guardan en tu carpeta. "
                      "Si activas el análisis con IA (Gemini u OpenAI), el TEXTO de la transcripción se envía "
                      "a los servidores de Google u OpenAI (que lo retienen temporalmente: Gemini hasta 55 días, "
                      "OpenAI sin usarlo para entrenar) para generar resúmenes, guías y exámenes. "
                      "Al grabar a otras personas, debes informarles de que la sesión se está grabando y "
                      "obtener su consentimiento cuando la ley lo exija. El contenido generado por IA es "
                      "informativo y puede contener errores: no lo uses como consejo médico, legal o profesional "
                      "ni como acta oficial.",
                  font=("Segoe UI", 11), text_color=C["muted"], wraplength=760, justify="left").pack(anchor="w", padx=20, pady=(0, 8))
        self.wiz_priv_ack = ctk.BooleanVar(value=False)
        self.wiz_ia_consent = ctk.BooleanVar(value=False)
        if CTK:
            ctk.CTkCheckBox(f4, text="✅ He leído y acepto el aviso de privacidad",
                            variable=self.wiz_priv_ack, font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=4)
            ctk.CTkCheckBox(f4, text="🤖 Permito el análisis con IA (el texto de mis transcripciones se enviará a Gemini/OpenAI — puedo desactivarlo en Configuración)",
                            variable=self.wiz_ia_consent, font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=4)
        else:
            ctk.Checkbutton(f4, text="He leido y acepto el aviso de privacidad",
                            variable=self.wiz_priv_ack, bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=4)
            ctk.Checkbutton(f4, text="Permito el analisis con IA (envio a Gemini/OpenAI)",
                            variable=self.wiz_ia_consent, bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=4)

        # (El boton "Comenzar" y la nota estan en la barra fija inferior)

    def _finish_wizard(self):
        # Guarda contra doble disparo (Enter rapido + clic en el boton): la
        # segunda llamada encontraria los widgets del asistente destruidos.
        if getattr(self, "_wiz_finishing", False):
            return
        self._wiz_finishing = True
        if not self.wiz_priv_ack.get():
            self._wiz_finishing = False
            self._msg("warning", "Aviso de privacidad",
                      "Para continuar, marca la casilla: He leído y acepto el aviso de privacidad.")
            return
        self.config["ia_consent"] = bool(self.wiz_ia_consent.get())
        self.config["rec_consent_ack"] = True
        self.config["audio_profile"] = self.wiz_profile.get()
        self.config["transcription_mode"] = self.wiz_mode.get()
        # 'nuevo' = Modo Guiado (vista simple); 'avanzado' = todo visible
        self.config["modo_guiado"] = (self.wiz_level.get() == "nuevo")
        gemini_key = self.wiz_gemini.get().strip()
        if gemini_key and len(gemini_key) > 10:
            self.config["gemini_api_key"] = gemini_key
        self.config["first_run"] = False
        save_config(self.config)

        self.pipeline = AudioPipeline(self.config["audio_profile"])
        self.adapt_engine = self._build_adapt_engine()

        self.wizard.destroy()
        self._build_main_ui()
        # Restaurar el tamano de ventana de la app completa (adaptativo)
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w = min(1450, max(900, sw))
            h = min(1050, max(600, sh - 70))
            px = max(0, (sw - w) // 2)
            py = max(0, (sh - 40 - h) // 2)
            self.geometry(f"{w}x{h}+{px}+{py}")
            self.minsize(1000, 620)
        except Exception:
            pass
        try:
            if CTK:
                self.configure(fg_color=C["bg"])
        except Exception:
            pass
        # Despues del asistente el siguiente paso debe ser obvio: toast verde
        # y el banner "Siguiente paso" con el boton rojo pulsando.
        self.after(600, lambda: self._show_toast("¡Configuración lista!"))
        self._update_next_step()

    def _build_main_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sb = self._frame(self, width=300, fg_color=C["card"])
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(15, 8),
                pady=8 if getattr(self, "_compact", False) else 15)
        sb.grid_propagate(False)

        self._lbl(sb, "🗂  Historial de Clases", font=(self.FH, 16, "bold"), text_color=C["text"]).pack(pady=(18, 12), padx=15, anchor="w")

        if CTK:
            hf = ctk.CTkScrollableFrame(sb, corner_radius=8, fg_color=C["card"])
        else:
            hf = ctk.Frame(sb, bg=C["card"])
        hf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.hist_frame = hf

        bf = self._frame(sb, fg_color="transparent")
        bf.pack(fill="x", padx=10, pady=(0, 15))

        self.bplay = self._btn(bf, "Reproducir", self._play, state="disabled", width=260, height=32, fg_color=C["accent"])
        self.bplay.pack(fill="x", pady=(0, 6))
        self.btransh = self._btn(bf, "Transcribir", self._transh, state="disabled", width=260, height=32)
        self.btransh.pack(fill="x", pady=(0, 6))
        self.bdel = self._btn(bf, "Eliminar", self._delh, state="disabled", width=260, height=32, fg_color=C["err"], hover_color=C["err"])
        self.bdel.pack(fill="x", pady=(0, 6))
        self.bcompile = self._btn(bf, "Compilar Todo", self._compile, state="disabled", width=260, height=32, fg_color=C["cloud"], hover_color=C["cloud"])
        self.bcompile.pack(fill="x", pady=(0, 6))
        self.bguide = self._btn(bf, "❓ Guía Rápida", self._open_guide, width=260, height=32, fg_color=C["accent"], hover_color=C["accent_hover"])
        self.bguide.pack(fill="x", pady=(0, 6))
        self.bconfig = self._btn(bf, "⚙️ Configuración", self._open_config, width=260, height=32)
        self.bconfig.pack(fill="x", pady=(0, 6))
        self.badv = self._btn(bf, "⚙️ Opciones avanzadas", self._toggle_advanced, width=260, height=32,
                              fg_color=C["cloud"], hover_color=C["cloud"])
        self.badv.pack(fill="x")

        mn = self._frame(self, fg_color=C["bg"])
        mn.grid(row=0, column=1, sticky="nsew", padx=(8, 15),
                pady=8 if getattr(self, "_compact", False) else 15)
        mn.grid_columnconfigure(0, weight=1)
        # SOLO la fila Gemini (6) flexa: cuando la ventana es corta, el grid
        # comprime las filas con weight por debajo de su tamano natural antes
        # que las fijas. Las filas esenciales (controls 2, waveform 5,
        # transcripcion 7) van SIN weight para conservar su tamano y que el
        # editor de transcripcion nunca quede colapsado o fuera de pantalla.
        mn.grid_rowconfigure(6, weight=1)

        hd = self._frame(mn, fg_color=C["header"], border_width=1, border_color=C["border"], theme_key="header")
        hd.grid(row=0, column=0, sticky="ew", padx=22, pady=(12, 6))
        hd.grid_columnconfigure(0, weight=1)
        brand = self._frame(hd, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(18, 8), pady=(1, 0))
        self._lbl(brand, "🎓", font=(self.FH, 24), text_color=C["head_text"], theme_key="head_text").pack(side="left", padx=(0, 12))
        btb = self._frame(brand, fg_color="transparent")
        btb.pack(side="left")
        self._lbl(btb, APP_NAME, font=(self.FH, 21, "bold"), text_color=C["head_text"], theme_key="head_text").pack(anchor="w")
        self._lbl(btb, "Grabación y transcripción académica con IA",
                  font=(self.FB, 11), text_color=C["head_text"], theme_key="head_text").pack(anchor="w")
        hdr = self._frame(hd, fg_color="transparent")
        hdr.grid(row=0, column=1, sticky="e", padx=(8, 16), pady=(8, 2))
        self.lconn = self._lbl(hdr, "🖥️ Motor local", font=(self.FB, 11), text_color=C["head_text"], theme_key="head_text")
        self.lconn.pack(side="left", padx=(0, 12))
        self.btheme_hd = self._btn(hdr, "🌙" if self.dark else "☀️", self._theme,
                                   width=44, height=34, font=(self.FB, 14),
                                   fg_color=C["card"], hover_color=C["border"])
        self.btheme_hd.pack(side="left")
        # Subrayado dorado institucional
        self.goldline = ctk.CTkFrame(hd, height=3, corner_radius=2, fg_color=C["accent"]) if CTK else ctk.Frame(hd, height=3, bg=C["accent"])
        self.goldline.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 8))
        try:
            self.goldline.grid_propagate(False)
        except Exception:
            pass

        # Indicador de flujo guiado: 4 pasos que se iluminan a medida que avanzas.
        # Cada paso es clicable: abre la Guia Rapida en su seccion.
        # NOTA: hd se gestiona con grid; nunca mezclar pack aqui.
        steps = self._frame(hd, fg_color="transparent")
        steps.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(2, 0))
        self.steps_frame = steps
        self.step_lbls = {}
        for i, (num, txt) in enumerate([("1", "Graba"), ("2", "Transcribe"), ("3", "Analiza"), ("4", "Guarda")]):
            paso = i + 1
            # Diseno: los pasos son pilulas con fondo; _set_step las rellena
            # con acento (actual), verde (completado) o gris (futuro).
            if CTK:
                lbl = ctk.CTkLabel(steps, text=f"  {num}. {txt}  ", font=(self.FB, 12, "bold"),
                                   text_color=C["muted"], fg_color=C["button"], corner_radius=12)
            else:
                lbl = ctk.Label(steps, text=f"  {num}. {txt}  ", font=(self.FB, 12, "bold"),
                                bg=C["button"], fg=C["muted"])
            lbl.pack(side="left", padx=(0, 14))
            lbl.bind("<Button-1>", lambda e, s=paso: self._open_guide(s))
            try:
                lbl.configure(cursor="hand2")
            except Exception:
                pass
            self.step_lbls[paso] = lbl
        # (La pista "pulsa un paso" se omite en pantallas cortas: el banner
        # "Siguiente paso" con su boton de ayuda ya guia al usuario.)
        self._set_step(1)

        # Banner permanente "Siguiente paso": tras el asistente y durante todo
        # el flujo, el usuario siempre sabe QUE hacer a continuacion. Se
        # actualiza solo con _update_next_step() segun el estado (grabar,
        # transcribir, analizar o guardar) y el boton de ayuda abre la Guia
        # Rapida en la seccion de ese paso. En modo compacto se omite (los
        # pasos clicables + el boton de ayuda de la barra lateral siguen
        # guiando) para que la transcripcion quepa en pantallas pequenas.
        self.next_step_frame = None
        if not getattr(self, "_compact", False):
            nx = self._frame(hd, fg_color=C["card"], border_width=2, border_color=C["accent"])
            nx.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 2))
            nx.grid_columnconfigure(0, weight=1)
            self.next_step_frame = nx
            self.lnext = self._lbl(nx, "", font=(self.FH, 15, "bold"), text_color=C["accent"],
                                   anchor="w", wraplength=1000)
            self.lnext.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=(6, 2))
            self.lnext_sub = self._lbl(nx, "", font=(self.FB, 11), text_color=C["muted"],
                                       anchor="w", wraplength=1000)
            self.lnext_sub.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 2))
            self._btn(nx, "❓ ¿Cómo se hace?", lambda: self._open_guide(self._next_guide_step or 1),
                      width=170, height=32, font=(self.FB, 11), fg_color=C["accent"],
                      hover_color=C["accent_hover"]).grid(row=0, column=1, rowspan=2, padx=(8, 16), pady=6)

        easy = self._frame(mn, fg_color=C["card"], border_width=2, border_color=C["easy"])
        easy.grid(row=1, column=0, sticky="ew", padx=22, pady=10)

        self._lbl(easy, "MODO FACIL", font=(self.FH, 16, "bold"), text_color=C["easy"]).pack(anchor="w", padx=18, pady=(2, 2))
        if not getattr(self, "_compact", False):
            self._lbl(easy, "Un solo boton hace TODO: Grabar → Procesar → Transcribir → Analizar Academicamente",
                       font=(self.FB, 11), text_color=C["muted"]).pack(anchor="w", padx=18, pady=(0, 4))

        easy_row = self._frame(easy, fg_color="transparent")
        easy_row.pack(fill="x", padx=18, pady=(0, 3))

        self.easy_var = ctk.BooleanVar(value=self.config.get("modo_facil", False))
        if CTK:
            self.easy_switch = ctk.CTkSwitch(easy_row, text="Activar Modo Facil", variable=self.easy_var,
                                             font=(self.FB, 12), command=self._toggle_easy,
                                             progress_color=C["easy"], button_color=C["easy"])
            self.easy_switch.pack(side="left", padx=(0, 20))
        else:
            self.easy_switch = ctk.Checkbutton(easy_row, text="Activar Modo Facil", variable=self.easy_var,
                                               bg=C["card"], fg=C["text"], command=self._toggle_easy)
            self.easy_switch.pack(side="left", padx=(0, 20))

        self.easy_template = ctk.StringVar(value=self.config.get("adaptacion_default", "Analisis Academico Profundo"))
        templates_list = list(GeminiAdaptationEngine.TEMPLATES.keys())
        if CTK:
            self.easy_menu = ctk.CTkOptionMenu(easy_row, values=templates_list,
                                               variable=self.easy_template, width=260, font=(self.FB, 11))
            self.easy_menu.pack(side="left", padx=(0, 10))
        else:
            self.easy_menu = ctk.OptionMenu(easy_row, self.easy_template, *templates_list)
            self.easy_menu.pack(side="left", padx=(0, 10))

        self._lbl(easy_row, "Selecciona que generar automaticamente",
                   font=(self.FB, 10), text_color=C["muted"]).pack(side="left")

        ct = self._frame(mn, fg_color=C["card"])
        ct.grid(row=2, column=0, sticky="ew", padx=22, pady=10)

        self.brec = self._btn(ct, "🎙️", self._togglerec, width=64, height=64, corner_radius=32,
                               font=(self.FB, 26), fg_color=C["mic"], hover_color=C["err"],
                               no_theme=True)
        self.brec.pack(side="left", padx=(18, 12), pady=10)

        self.bstop = self._btn(ct, "🛑 Detener", self._stoprec, width=150, height=52,
                                font=(self.FB, 14, "bold"), fg_color=C["err"], hover_color=C["err"])
        self.bstop.pack(side="left", padx=(0, 12), pady=10)
        self.bstop.pack_forget()

        self.btr = self._btn(ct, "📝 Transcribir", lambda: self._starttrans(False), width=150, height=42, state="disabled")
        self.btr.pack(side="left", padx=(0, 8), pady=10)
        self.bts = self._btn(ct, "⏱️ Con tiempos", lambda: self._starttrans(True), width=130, height=42, state="disabled")
        self.bts.pack(side="left", padx=(0, 8), pady=10)
        self.bpdf = self._btn(ct, "📄 Guardar PDF", self._pdf, width=130, height=42, state="disabled")
        self.bpdf.pack(side="left", padx=(0, 8), pady=10)
        self.bdocx = self._btn(ct, "📝 Guardar DOCX", self._export_docx, width=140, height=42, state="disabled")
        self.bdocx.pack(side="left", padx=(0, 8), pady=10)
        self.bdocs = self._btn(ct, "🌐 Google Docs", self._export_docs, width=140, height=42, state="disabled",
                                fg_color=C["ok"], hover_color=C["ok"])
        # Si el componente OAuth no esta disponible (exe de distribucion), el
        # boton queda desactivado con etiqueta clara en vez de fallar al pulsar.
        if not _gdocs_importable():
            self.bdocs.configure(text="🌐 Google Docs (no disponible)", width=180)
        self.bdocs.pack(side="left", padx=(0, 8), pady=10)
        self.bcancel = self._btn(ct, "Cancelar", self._cancel, width=100, height=42, state="disabled",
                                  fg_color=C["err"], hover_color=C["err"])
        self.bcancel.pack(side="left", padx=(0, 18), pady=10)

        # Medidor de nivel de entrada (VU meter) visible durante la grabacion:
        # barra + dB en vivo + historico de los ultimos 10 s (mini-grafico) +
        # deslizador de sensibilidad para la deteccion de "audio sin voz".
        # Se actualiza desde el hilo principal (_updvu).
        vu = self._frame(ct, fg_color="transparent")
        vu.pack(side="left", padx=(0, 14), pady=12)
        vu_row1 = self._frame(vu, fg_color="transparent")
        vu_row1.pack(side="top", fill="x")
        self._lbl(vu_row1, "🎚", font=("Segoe UI", 12)).pack(side="left", padx=(0, 6))
        if CTK:
            self.vu_bar = ctk.CTkProgressBar(vu_row1, width=170, height=10, corner_radius=5,
                                             fg_color=C["button"], progress_color=C["accent"])
            self.vu_bar.set(0)
            self._gold_bars.append(self.vu_bar)
        else:
            self.vu_bar = ttk.Progressbar(vu_row1, mode="determinate", length=150, maximum=100)
            self.vu_bar['value'] = 0
        self.vu_bar.pack(side="left", padx=(0, 8))
        self.vu_lbl = self._lbl(vu_row1, "-∞ dB", font=("Segoe UI", 10), text_color=C["muted"])
        self.vu_lbl.pack(side="left")
        # Aviso de "audio sin voz" (estatica) mientras se graba: aparece cuando
        # el nivel es constante sin variacion (ruido de fondo / micro danado)
        self.vu_warn = self._lbl(vu_row1, "", font=("Segoe UI", 10), text_color=C["warn"])
        self.vu_warn.pack(side="left", padx=(8, 0))

        # Fila 2: historico visual de los ultimos 10 s (125 lecturas de 80 ms)
        # + deslizador de sensibilidad (umbral de coeficiente de variacion).
        vu_row2 = self._frame(vu, fg_color="transparent")
        vu_row2.pack(side="top", fill="x", pady=(4, 0))
        self.vu_hist = tk.Canvas(vu_row2, width=160, height=24, bg=C["card"],
                                 highlightthickness=1, highlightbackground=C["border"])
        self.vu_hist.pack(side="left", padx=(0, 6))
        self._lbl(vu_row2, "Sens:", font=("Segoe UI", 9), text_color=C["muted"]).pack(side="left", padx=(0, 4))
        if CTK:
            self.vu_sens_slider = ctk.CTkSlider(vu_row2, from_=0.05, to=0.60,
                                                number_of_steps=11, command=self._vu_sens_changed,
                                                width=110, height=16,
                                                progress_color=C["accent"], button_color=C["accent"])
        else:
            self.vu_sens_slider = ttk.Scale(vu_row2, from_=0.05, to=0.60, orient="horizontal",
                                            command=self._vu_sens_changed, length=110)
        self.vu_sens_slider.set(self.vu_sens)
        self.vu_sens_slider.pack(side="left", padx=(0, 6))
        self.vu_sens_val = self._lbl(vu_row2, f"{self.vu_sens:.2f}", font=("Segoe UI", 9), text_color=C["muted"])
        self.vu_sens_val.pack(side="left")

        # El estado se muestra fuera del frame de configuracion para que siga
        # visible en Modo Guiado (que oculta Perfil/Motor/Modelo)
        self.lstatus = self._lbl(ct, "Listo para grabar", font=("Segoe UI", 12), text_color=C["muted"])
        self.lstatus.pack(side="right", padx=(20, 18), pady=10)

        cfg = self._frame(mn, fg_color=C["card"])
        cfg.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))
        self.cfg_frame = cfg

        # Resumen de la configuracion activa: ocupa la misma fila que los
        # controles (Perfil/Motor/Modelo) y se muestra cuando el Modo Guiado
        # los oculta, para que el usuario sepa que hay sin ver los controles.
        cfg_sum = self._frame(mn, fg_color=C["card"])
        cfg_sum.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 4))
        self.cfg_sum_frame = cfg_sum
        self.lcfg_sum = self._lbl(cfg_sum, "", font=("Segoe UI", 11), text_color=C["muted"])
        self.lcfg_sum.pack(anchor="w", padx=18, pady=3)

        self._lbl(cfg, "Perfil:", font=("Segoe UI", 12)).pack(side="left", padx=(18, 6), pady=12)
        self.profile_var = ctk.StringVar(value=self.config.get("audio_profile", "Clase Universitaria"))
        if CTK:
            self.cmb_profile = ctk.CTkOptionMenu(cfg, values=list(AudioPipeline.PROFILES.keys()),
                                                  variable=self.profile_var, width=180,
                                                  command=self._chprofile, font=("Segoe UI", 11))
        else:
            self.cmb_profile = ctk.OptionMenu(cfg, self.profile_var, *AudioPipeline.PROFILES.keys(), command=self._chprofile)
        self.cmb_profile.pack(side="left", padx=(0, 20), pady=12)

        self._lbl(cfg, "Motor:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 6), pady=12)
        self.mode_var = ctk.StringVar(value=self.config.get("transcription_mode", "local"))
        if CTK:
            # Radiobuttons en vez de segmented: CTkSegmentedButton aplica UN
            # solo text_color a todos los segmentos, y el acento (activo) y el
            # fondo (inactivo) exigen colores opuestos (blanco/negro) — con un
            # solo color uno de los dos estados queda <4.5:1. Los radiobuttons
            # tienen texto propio por opcion y cumplen WCAG en ambos estados.
            for val, lbl in (("local", "Local"), ("cloud", "Cloud")):
                rb = ctk.CTkRadioButton(cfg, text=lbl, variable=self.mode_var, value=val,
                                        command=self._chmode, font=("Segoe UI", 11),
                                        text_color=C["text"])
                rb.pack(side="left", padx=(0, 14), pady=12)
                # Registrar para re-tematizar el texto al cambiar claro/oscuro
                self._themeable.append(("label", rb, "text"))
        else:
            ctk.OptionMenu(cfg, self.mode_var, "local", "cloud", command=self._chmode).pack(side="left", padx=(0, 20), pady=12)

        self._lbl(cfg, "Modelo:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 6), pady=12)
        self.model_var = ctk.StringVar(value=self.config.get("local_model", "base"))
        if CTK:
            self.cmb_model = ctk.CTkOptionMenu(cfg, values=["tiny", "base", "small"], 
                                                variable=self.model_var, width=90,
                                                command=self._chlocalmodel, font=("Segoe UI", 11))
        else:
            self.cmb_model = ctk.OptionMenu(cfg, self.model_var, "tiny", "base", "small", command=self._chlocalmodel)
        self.cmb_model.pack(side="left", padx=(0, 20), pady=12)

        # Idioma de whisper: "auto" detecta el idioma del audio (para
        # grabaciones en otro idioma o TTS); un codigo ISO lo fuerza.
        self._lbl(cfg, "Idioma:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 6), pady=12)
        self.lang_var = ctk.StringVar(value=self.config.get("whisper_language", "auto"))
        _langs = ["auto", "es", "en", "pt", "fr", "de", "it"]
        if CTK:
            self.cmb_lang = ctk.CTkOptionMenu(cfg, values=_langs, variable=self.lang_var,
                                              width=82, command=self._chlang, font=("Segoe UI", 11))
        else:
            self.cmb_lang = ctk.OptionMenu(cfg, self.lang_var, *_langs, command=self._chlang)
        self.cmb_lang.pack(side="left", padx=(0, 20), pady=12)

        self.fast_var = ctk.BooleanVar(value=False)
        if CTK:
            ctk.CTkSwitch(cfg, text="Rapido", variable=self.fast_var, font=("Segoe UI", 11)).pack(side="left", padx=(0, 15), pady=12)
        else:
            ctk.Checkbutton(cfg, text="Rapido", variable=self.fast_var, bg=C["card"], fg=C["text"]).pack(side="left", padx=(0, 15), pady=12)

        self.vad_var = ctk.BooleanVar(value=True)
        if CTK:
            ctk.CTkSwitch(cfg, text="VAD", variable=self.vad_var, font=("Segoe UI", 11),
                          progress_color=C["ok"]).pack(side="left", padx=(0, 15), pady=12)
        else:
            ctk.Checkbutton(cfg, text="VAD", variable=self.vad_var, bg=C["card"], fg=C["text"]).pack(side="left", padx=(0, 15), pady=12)

        self.btheme = self._btn(cfg, "Claro", self._theme, width=90, height=32)
        self.btheme.pack(side="left", pady=12)

        pr = self._frame(mn, fg_color=C["card"])
        pr.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 10))
        self.lprog = self._lbl(pr, "", font=("Segoe UI", 11), text_color=C["muted"])
        self.lprog.pack(anchor="w", padx=18, pady=(12, 4))
        if CTK:
            self.pbar = ctk.CTkProgressBar(pr, height=12, corner_radius=6,
                                           progress_color=C["accent"], fg_color=C["button"])
            self.pbar.set(0)
            self._gold_bars.append(self.pbar)
        else:
            self.pbar = ttk.Progressbar(pr, mode="determinate")
            self.pbar['value'] = 0
        self.pbar.pack(fill="x", padx=18, pady=(0, 14))

        vz = self._frame(mn, fg_color=C["card"])
        vz.grid(row=5, column=0, sticky="nsew", padx=22, pady=(0, 6))

        if MPL:
            # Waveform compacto: ~150px en vez de ~240px para que el editor de
            # transcripcion quepa en pantallas pequenas.
            self.fig = Figure(figsize=(8, 0.6 if getattr(self, "_compact", False) else 1.5),
                              dpi=100, facecolor=C["card"])
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor(C["card"])
            self.ax.tick_params(colors=C["muted"], labelsize=8)
            for sp in self.ax.spines.values(): sp.set_color(C["border"])
            self.ax.set_ylim(-0.5, 0.5)
            self.ax.set_xlim(0, VISUAL_SAMPLES)
            self.ax.set_xticks([])
            self.line, = self.ax.plot([], [], color=C["accent"], linewidth=1.8)
            self.canvas = FigureCanvasTkAgg(self.fig, master=vz)
            self.canvas.draw()
            self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=6)
        else:
            self._lbl(vz, "Instala matplotlib: pip install matplotlib", text_color=C["warn"]).pack(pady=35)

        adapt = self._frame(mn, fg_color=C["card"], border_width=1, border_color=C["gemini"])
        adapt.grid(row=6, column=0, sticky="nsew", padx=22, pady=(0, 18))
        adapt.grid_rowconfigure(2, weight=1)
        adapt.grid_columnconfigure(0, weight=1)

        ah = self._frame(adapt, fg_color="transparent")
        ah.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        self._lbl(ah, "Adaptacion Inteligente", font=("Segoe UI", 14, "bold"), text_color=C["gemini"]).pack(side="left")
        self.ladapt = self._lbl(ah, "Sin API Key", font=("Segoe UI", 11), text_color=C["warn"])
        self.ladapt.pack(side="right")

        self._lbl(adapt, "Selecciona que quieres generar a partir de la transcripcion:",
                   font=("Segoe UI", 11), text_color=C["muted"]).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 8))

        btn_frame = self._frame(adapt, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 10))

        self.adapt_buttons = {}
        self.adapt_extra = []  # plantillas adicionales (se ocultan en Modo Guiado)
        templates = list(GeminiAdaptationEngine.TEMPLATES.items())
        for idx, (name, info) in enumerate(templates):
            row, col = divmod(idx, 4)
            b = self._btn(btn_frame, f"{info['icon']} {name}", 
                          lambda n=name: self._adapt(n),
                          width=170, height=38, state="disabled",
                          fg_color=C["button"], hover_color=C["border"])
            b.grid(row=row, column=col, padx=6, pady=6)
            self.adapt_buttons[name] = b
            if idx > 0:  # la primera plantilla (Analisis Academico Profundo) es la esencial
                self.adapt_extra.append(b)

        self.adapt_info = self._lbl(adapt, "", font=("Segoe UI", 10), text_color=C["muted"])
        self.adapt_info.grid(row=3, column=0, sticky="w", padx=18, pady=(0, 4))

        if CTK:
            self.adapt_txt = ctk.CTkTextbox(adapt, font=("Consolas", 11), wrap="word", corner_radius=8,
                                             fg_color=C["bg"], text_color=C["text"], height=140)
        else:
            self.adapt_txt = scrolledtext.ScrolledText(adapt, wrap=ctk.WORD, font=("Consolas", 11), 
                                                        bg=C["bg"], fg=C["text"], height=7)
        self.adapt_txt.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 14))
        self.adapt_txt.configure(state="disabled")

        self.bsave_adapt = self._btn(adapt, "Guardar Adaptacion", self._save_adaptation,
                                      width=180, height=36, state="disabled")
        self.bsave_adapt.grid(row=5, column=0, sticky="w", padx=18, pady=(0, 12))

        tr = self._frame(mn, fg_color=C["card"], border_width=1, border_color=C["border"])
        tr.grid(row=7, column=0, sticky="nsew", padx=22, pady=(0, 5))
        tr.grid_rowconfigure(1, weight=1)
        tr.grid_columnconfigure(0, weight=1)

        th = self._frame(tr, fg_color="transparent")
        th.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        self._lbl(th, "Transcripción", font=(self.FH, 15, "bold"), text_color=C["text"]).pack(side="left")
        self.lbadge = self._lbl(th, "✓ Revisado por IA", font=(self.FB, 10, "bold"), text_color=C["ok"])
        self.lbadge.pack(side="right", padx=(0, 14))
        self.lbadge.pack_forget()
        self._btn(th, "📋 Copiar", self._copy_trans, width=92, height=28, font=(self.FB, 10),
                  fg_color=C["button"], hover_color=C["border"]).pack(side="right", padx=(0, 14))
        self.lmodel = self._lbl(th, "Cargando...", font=(self.FB, 11), text_color=C["warn"])
        self.lmodel.pack(side="right")

        tbox = self._frame(tr, fg_color=C["bg"], border_width=1, border_color=C["border"])
        tbox.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 14))
        tbox.grid_rowconfigure(0, weight=1)
        tbox.grid_columnconfigure(1, weight=1)

        # Gutter de numeros de linea (estilo editor de codigo)
        # height=8 igual que el editor: sin esto el gutter pedía 24 lineas
        # (~408px) y la fila de transcripcion empujaba el resto fuera de pantalla.
        self.txt_gutter = tk.Text(tbox, width=4, wrap="none", state="disabled",
                                  height=5 if getattr(self, "_compact", False) else 8,
                                  bg=C["card"], fg=C["muted"], font=(self.FM, 11),
                                  padx=6, pady=8, relief="flat", borderwidth=0,
                                  highlightthickness=0, takefocus=0)
        self.txt_gutter.grid(row=0, column=0, sticky="nsew")

        # Area de transcripcion: tk.Text (permite tags + gutter) estilo codigo
        # Altura compacta (6 lineas en pantallas pequenas, 8 en grandes): el
        # editor nunca pide las 24 lineas por defecto (que empujaban la
        # transcripcion fuera de pantalla).
        self.txt = tk.Text(tbox, wrap="word", state="disabled",
                           height=5 if getattr(self, "_compact", False) else 8,
                           bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                           font=(self.FM, 11), padx=12, pady=8,
                           relief="flat", borderwidth=0, highlightthickness=0)
        self.txt.grid(row=0, column=1, sticky="nsew")
        self.txt.configure(yscrollcommand=self._txt_yscroll)
        self.txt.tag_configure("live", foreground=C["accent"])
        self.txt.tag_configure("head", foreground=C["accent"], font=(self.FM, 11, "bold"))
        self.vsb = tk.Scrollbar(tbox, orient="vertical", command=self.txt.yview,
                                bg=C["border"], troughcolor=C["bg"], relief="flat")
        self.vsb.grid(row=0, column=2, sticky="ns")
        self._fill_gutter()

        ft = self._frame(mn, fg_color=C["card"], border_width=1, border_color=C["border"])
        ft.grid(row=8, column=0, sticky="ew", padx=22, pady=(0, 5))
        ftl = self._frame(ft, fg_color="transparent")
        ftl.pack(side="left")
        self._lbl(ftl, f"📁 {OUTPUT_DIR}", font=(self.FB, 10), text_color=C["muted"]).pack(side="left")
        self._lbl(ft, "Espacio ▶  ·  Ctrl+R grabar  ·  Ctrl+S guardar  ·  Ctrl+E exportar  ·  F1 ayuda",
                  font=(self.FB, 10), text_color=C["muted"]).pack(side="right", padx=(0, 18))
        self._btn(ftl, "📂 Abrir carpeta", self._open_output_dir, width=130, height=28,
                  font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))
        self._btn(ftl, "🎤 Probar micrófono", self._test_mic, width=170, height=28,
                  font=("Segoe UI", 10), fg_color=C["accent"], hover_color=C["accent_hover"]).pack(side="left", padx=(8, 0))
        self._btn(ftl, "🎛️ Optimizar micrófono", self._open_mic_opt, width=195, height=28,
                  font=("Segoe UI", 10), fg_color=C["ok"], hover_color=C["ok"]).pack(side="left", padx=(8, 0))
        self.ltime = self._lbl(ft, "", font=("Segoe UI", 10), text_color=C["muted"])
        self.ltime.pack(side="right")

        self._loadhist()
        self._update_adapt_status()
        self._chmode(self.mode_var.get())
        self.local_engine.load(callback=self._on_model_loaded)
        self._apply_guided()
        self._update_next_step()
        self._bind_shortcuts()

    def _toggle_easy(self):
        self.config["modo_facil"] = self.easy_var.get()
        self.config["adaptacion_default"] = self.easy_template.get()
        save_config(self.config)

    def _set_panel_visible(self, frame, visible):
        """Muestra u oculta un frame colocado con grid conservando su configuracion.
        Guarda grid_info() antes de ocultar para poder restaurarlo despues."""
        try:
            if visible:
                info = getattr(frame, "_grid_restore", None)
                if info:
                    frame.grid(**info)
            else:
                if frame.winfo_manager() == "grid":
                    info = frame.grid_info()
                    # 'in' es la ruta del padre; no se pasa de vuelta a grid()
                    frame._grid_restore = {k: v for k, v in info.items() if k != "in"}
                    frame.grid_remove()
        except Exception:
            pass

    def _apply_guided(self):
        """Aplica el Modo Guiado: oculta los paneles avanzados (Perfil/Motor/Modelo
        y plantillas de adaptacion extra) y deja solo lo esencial."""
        guided = bool(self.config.get("modo_guiado", True))
        try:
            if hasattr(self, "cfg_frame"):
                self._set_panel_visible(self.cfg_frame, not guided)
            if hasattr(self, "cfg_sum_frame"):
                self._set_panel_visible(self.cfg_sum_frame, guided)
                if guided:
                    self._update_cfg_summary()
            for b in getattr(self, "adapt_extra", []):
                self._set_panel_visible(b, not guided)
            if hasattr(self, "badv"):
                self.badv.configure(text=("⚙️ Opciones avanzadas" if guided else "🧭 Modo Guiado"))
        except Exception:
            pass

    def _update_cfg_summary(self):
        """Actualiza el texto resumen de la configuracion activa
        (perfil, motor y modelo) que se muestra en Modo Guiado."""
        perfil = self.config.get("audio_profile", "Clase Universitaria")
        modo = self.config.get("transcription_mode", "local")
        if modo == "cloud":
            modelo = self.config.get("cloud_model", "large-v3")
        else:
            modelo = self.config.get("local_model", "base")
        txt = f"Usando perfil: {perfil} · motor: {modo} · modelo: {modelo} · idioma: {self.config.get('whisper_language', 'auto')}"
        try:
            if hasattr(self, "lcfg_sum") and self.lcfg_sum.winfo_exists():
                self.lcfg_sum.configure(text=txt)
        except Exception:
            pass

    def _toggle_advanced(self):
        """Alterna entre Modo Guiado (solo lo esencial) y vista completa."""
        self.config["modo_guiado"] = not bool(self.config.get("modo_guiado", True))
        save_config(self.config)
        self._apply_guided()
        estado = "activado" if self.config["modo_guiado"] else "desactivado"
        self.q.put(("log", f"\nModo Guiado {estado}.\n"))

    def _chprofile(self, name):
        self.config["audio_profile"] = name
        save_config(self.config)
        self.pipeline = AudioPipeline(name, self.fast_var.get(), self.vad_var.get())
        self._update_cfg_summary()
        self._apptxt(f"\nPerfil cambiado a: {name}\n")

    def _chmode(self, mode):
        self.config["transcription_mode"] = mode
        save_config(self.config)
        self._update_cfg_summary()
        # El label de conexion vive en el header (fondo oscuro en ambos temas),
        # asi que su texto siempre va en head_text (claro) para mantener contraste.
        if mode == "local":
            self.cmb_model.configure(state="normal")
            self.lmodel.configure(text=f"Local: {self.model_var.get()}", text_color=C["muted"])
            if hasattr(self, "lconn"):
                self.lconn.configure(text=f"🖥️ Motor local · {self.model_var.get()}", text_color=C["head_text"])
        else:
            self.cmb_model.configure(state="disabled")
            if self.config.get("colab_url"):
                self.lmodel.configure(text="Cloud: Colab GPU", text_color=C["cloud"])
                if hasattr(self, "lconn"):
                    self.lconn.configure(text="☁️ Motor Cloud · GPU", text_color=C["head_text"])
            else:
                self.lmodel.configure(text="Cloud: Sin URL", text_color=C["warn"])
                if hasattr(self, "lconn"):
                    self.lconn.configure(text="☁️ Motor Cloud · sin URL", text_color=C["head_text"])

    def _chlocalmodel(self, name):
        self.config["local_model"] = name
        save_config(self.config)
        self.local_engine = LocalWhisperEngine(
            name, self.config.get("whisper_language", "auto"))
        self._update_cfg_summary()
        self.local_engine.load(callback=self._on_model_loaded)
        self.lmodel.configure(text=f"Cargando {name}...", text_color=C["warn"])

    def _chlang(self, name):
        """Cambia el idioma de whisper: 'auto' detecta solo, ISO lo fuerza.
        Aplica a ambos motores (local y cloud) y no recarga el modelo (el
        idioma se resuelve en cada transcribe)."""
        self.config["whisper_language"] = name
        save_config(self.config)
        if hasattr(self, "local_engine"):
            self.local_engine.language = name
        if hasattr(self, "cloud_engine"):
            self.cloud_engine.language = name
        self._update_cfg_summary()
        self._apptxt(f"\nIdioma de transcripción: {'auto (detecta el idioma)' if name == 'auto' else name}\n")

    def _on_model_loaded(self, status, msg):
        if status == "ready":
            self.q.put(("model_ready", msg))
        else:
            self.q.put(("model_err", msg))

    def _build_adapt_engine(self):
        """Motor de adaptacion segun el proveedor elegido (gemini por defecto)."""
        if self.config.get("adapt_provider", "gemini") == "openai":
            return OpenAIAdaptationEngine(
                self.config.get("openai_api_key", ""),
                self.config.get("openai_model", "mini")
            )
        return GeminiAdaptationEngine(
            self.config.get("gemini_api_key", ""),
            self.config.get("gemini_model", "flash")
        )

    def _update_adapt_status(self):
        if not hasattr(self, "ladapt"):
            return
        prov = self.config.get("adapt_provider", "gemini")
        if prov == "openai":
            key = self.config.get("openai_api_key", "")
            label = "OpenAI"
        else:
            key = self.config.get("gemini_api_key", "")
            label = "Gemini"
        if key and len(key) > 10:
            self.ladapt.configure(text=f"{label} listo", text_color=C["ok"])
        else:
            self.ladapt.configure(text="Sin API Key", text_color=C["warn"])

    def _set_step(self, n):
        """Ilumina el paso actual del flujo guiado (1=Graba, 2=Transcribe, 3=Analiza, 4=Guarda)."""
        self._cur_step = n
        if not hasattr(self, "step_lbls") or not self.step_lbls:
            return
        for step, lbl in self.step_lbls.items():
            # Pilulas: el paso actual se rellena con el acento, los completados
            # se marcan en verde y los futuros quedan en gris.
            try:
                if CTK:
                    if step == n:
                        lbl.configure(text_color=_btn_text_color(C["accent"]),
                                      fg_color=C["accent"])
                    elif step < n:
                        lbl.configure(text_color=C["ok"], fg_color=C["button"])
                    else:
                        lbl.configure(text_color=C["text"], fg_color=C["button"])
                else:
                    lbl.configure(fg=(_btn_text_color(C["accent"]) if step == n else (C["ok"] if step < n else C["text"])),
                                  bg=(C["accent"] if step == n else C["button"]))
            except Exception:
                pass
        # Mantener el banner "Siguiente paso" sincronizado con el paso actual
        self._update_next_step()

    def _update_next_step(self):
        """Actualiza el banner "Siguiente paso" segun el estado real del flujo:
        1=Grabar, 2=Transcribir, 3=Analizar, 4=Guardar. Tambien enciende o
        apaga el pulso del boton rojo cuando toca grabar."""
        if not hasattr(self, "lnext"):
            return
        try:
            if not self.lnext.winfo_exists():
                return
        except Exception:
            return
        rec = bool(self.recording)
        has_audio = bool(self.last_path)
        has_text = bool(self.last_text)
        has_adapt = False
        try:
            has_adapt = bool(self.adapt_txt.get("1.0", "end").strip())
        except Exception:
            pass
        if self.config.get("adapt_provider", "gemini") == "openai":
            has_key = bool(self.config.get("openai_api_key", ""))
        else:
            has_key = bool(self.config.get("gemini_api_key", ""))

        if rec:
            main = "🛑 Estás grabando..."
            sub = "Cuando termines tu clase pulsa el botón amarillo: DETENER."
            col, step = C["warn"], 1
        elif not has_audio:
            main = "🎙️ Pulsa el botón rojo: GRABAR MI CLASE"
            sub = "Habla con normalidad. Cuando termines pulsa 🛑 DETENER."
            col, step = C["err"], 1
        elif not has_text:
            main = "📝 Pulsa el botón: TRANSCRIBIR"
            sub = "AudioClass convierte la voz del profesor en texto. Funciona sin internet."
            col, step = C["accent"], 2
        elif not has_adapt:
            if has_key:
                main = "🎓 Pulsa: ANÁLISIS ACADÉMICO PROFUNDO"
                sub = "Gemini convierte tu transcripción en apuntes: resumen, tesis, datos clave."
                col, step = C["academic"], 3
            else:
                main = "🎓 Añade tu API Key de IA (Gemini u OpenAI)"
                sub = "Configuración → elige tu proveedor de IA y pega tu API Key para analizar tus clases."
                col, step = C["gemini"], 3
        else:
            main = "📄 ¡Clase lista! Guárdala o compártela"
            sub = "Pulsa GUARDAR PDF o 🌐 GOOGLE DOCS para tener tus apuntes en un archivo."
            col, step = C["ok"], 4

        self._next_guide_step = step
        try:
            self.lnext.configure(text=main, text_color=col)
            self.lnext_sub.configure(text=sub)
            self.next_step_frame.configure(border_color=col)
        except Exception:
            pass
        # Pulso del boton rojo solo cuando el siguiente paso es grabar
        if step == 1 and not rec:
            self._start_pulse_rec()
        else:
            self._stop_pulse_rec()

    def _start_pulse_rec(self):
        """Animacion suave: el boton rojo de grabar parpadea para llamar la
        atencion cuando es el siguiente paso. Se detiene al grabar o al
        cambiar de paso."""
        if not hasattr(self, "brec"):
            return
        self._stop_pulse_rec()
        self._pulse_active = True
        self._pulse_on = False

        def _tick():
            if not getattr(self, "_pulse_active", False):
                return
            try:
                if not self.brec.winfo_exists():
                    self._pulse_active = False
                    return
            except Exception:
                self._pulse_active = False
                return
            if self.recording:
                self._pulse_active = False
                return
            self._pulse_on = not self._pulse_on
            col = C["err"] if self._pulse_on else C["mic"]
            try:
                self.brec.configure(fg_color=col, hover_color=C["err"])
            except Exception:
                pass
            self._pulse_after = self.after(450, _tick)

        self._pulse_after = self.after(300, _tick)

    def _stop_pulse_rec(self):
        self._pulse_active = False
        if getattr(self, "_pulse_after", None):
            try:
                self.after_cancel(self._pulse_after)
            except Exception:
                pass
            self._pulse_after = None
        try:
            if hasattr(self, "brec") and self.brec.winfo_exists():
                self.brec.configure(fg_color=C["mic"], hover_color=C["err"])
        except Exception:
            pass

    def _show_toast(self, msg, kind="ok", retry=None):
        """Muestra un toast animado (ok/err/warn) junto al indicador de pasos.
        kind='err' admite 'Reintentar': boton que invoca la callback retry.
        Animacion: entra deslizandose con pulso, permanece ~1.5 s y se desvanece."""
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

        # Toasts: colores de paleta por modo (dark/light) para que el texto
        # siempre tenga contraste y siga el tema (antes hex literales fijos).
        _PILL = {
            "ok":   ("#0F172A", "#7DD3FC"),
            "err":  ("#450A0A", "#FCA5A5"),
            "warn": ("#451A03", "#FDE68A"),
        }
        _PILL_LIGHT = {
            "ok":   ("#E0F2FE", "#075985"),
            "err":  ("#FEE2E2", "#991B1B"),
            "warn": ("#FEF3C7", "#92400E"),
        }
        _PULSE = {"ok": C["accent"], "err": C["err"], "warn": C["warn"]}
        pill_bg, pill_fg = (_PILL if self.dark else _PILL_LIGHT).get(kind, (_PILL if self.dark else _PILL_LIGHT)["ok"])
        pulse_col = _PULSE.get(kind, C["accent"])
        self._toast_btn = None
        if CTK:
            lbl = ctk.CTkLabel(self.steps_frame, text="✓ " + msg,
                               font=("Segoe UI", 12, "bold"),
                               text_color=pill_fg, fg_color=pill_bg,
                               corner_radius=10, padx=12, pady=3)
        else:
            lbl = ctk.Label(self.steps_frame, text="✓ " + msg,
                            font=("Segoe UI", 12, "bold"),
                            bg=pill_bg, fg=pill_fg, padx=12, pady=3)
        lbl.pack(side="left", padx=(42, 0))  # comienza desplazado a la derecha
        self._toast_lbl = lbl
        color_opt = "text_color" if CTK else "fg"
        bg_opt = "fg_color" if CTK else "bg"
        page_bg = C["bg"]  # fondo de la pagina, para el desvanecido final

        if retry is not None:
            def _do_retry():
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
                rb = ctk.CTkButton(self.steps_frame, text="Reintentar", command=_do_retry,
                                   width=84, height=26, corner_radius=8,
                                   font=("Segoe UI", 10, "bold"),
                                   fg_color=pill_fg, text_color=pill_bg,
                                   hover_color=pulse_col)
            else:
                rb = ctk.Button(self.steps_frame, text="Reintentar", command=_do_retry,
                                bg=pill_fg, fg=pill_bg, font=("Segoe UI", 10, "bold"))
            rb.pack(side="left", padx=(6, 0))
            self._toast_btn = rb

        def _lerp(c1, c2, t):
            r1, g1, b1 = (int(c1[i:i + 2], 16) for i in (1, 3, 5))
            r2, g2, b2 = (int(c2[i:i + 2], 16) for i in (1, 3, 5))
            return "#%02x%02x%02x" % (int(r1 + (r2 - r1) * t),
                                      int(g1 + (g2 - g1) * t),
                                      int(b1 + (b2 - b1) * t))

        def _pulse(step, total=8):
            lbl2 = getattr(self, "_toast_lbl", None)
            if lbl2 is None or not lbl2.winfo_exists():
                return
            try:
                # Deslizarse hasta la posicion final (junto al indicador)
                padx_left = max(8, 42 - int(34 * step / total))
                lbl2.pack_configure(padx=(padx_left, 0))
                # Pulso: alterna entre dos tonos del color del toast
                lbl2.configure(**{color_opt: pulse_col if step % 2 == 0 else pill_fg})
            except Exception:
                return
            if step < total:
                self._toast_after = self.after(35, lambda: _pulse(step + 1))
            else:
                lbl2.configure(**{color_opt: pill_fg})
                # Los toasts de error con Reintentar duran mas para dar tiempo a leerlos
                self._toast_after = self.after(4500 if kind == "err" else 1500, _fade)

        def _fade(step=0, total=8):
            lbl2 = getattr(self, "_toast_lbl", None)
            if lbl2 is None or not lbl2.winfo_exists():
                return
            try:
                # Desvanecer el texto hacia el fondo de la insignia y el fondo
                # de la insignia hacia el fondo de la pagina (salida suave)
                # min(1.0, ...) evita que el ultimo frame (step == total)
                # genere colores hex invalidos por extrapolacion
                t = min(1.0, (step + 1) / total)
                lbl2.configure(**{color_opt: _lerp(pill_fg, pill_bg, t),
                                  bg_opt: _lerp(pill_bg, page_bg, t)})
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

    def _open_guide(self, step=None):
        """Ventana de ayuda en lenguaje simple. Si step (1-4) se indica,
        salta a la seccion correspondiente de ese paso en la guia."""
        # Si la ventana ya esta abierta, reutilizarla y saltar a la seccion
        if getattr(self, "_guide_top", None) is not None:
            try:
                if self._guide_top.winfo_exists():
                    self._guide_top.lift()
                    self._guide_top.focus_force()
                    if step is not None:
                        self._jump_guide(step)
                    return
            except Exception:
                pass

        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("Guía Rápida — AudioClass")
        top.geometry("760x680")
        top.transient(self)
        top.lift()
        # Sin grab_set: la guia no es modal, asi puedes pulsar otro paso
        # del indicador para saltar entre secciones mientras esta abierta.

        if CTK:
            box = ctk.CTkTextbox(top, font=("Segoe UI", 12), wrap="word", corner_radius=8,
                                 fg_color=C["bg"], text_color=C["text"])
        else:
            box = scrolledtext.ScrolledText(top, wrap=ctk.WORD, font=("Segoe UI", 12), bg=C["bg"], fg=C["text"])
        box.pack(fill="both", expand=True, padx=18, pady=(18, 8))

        guia = """¿CÓMO USAR AUDIOCLASS? (sin saber de computadoras)

AudioClass hace 3 cosas por ti:
1. GRABA tu clase con el micrófono.
2. TRANSCRIBE lo que dijo el profesor (convierte la voz en texto).
3. ANALIZA el texto con inteligencia artificial (resúmenes, guías, exámenes).

──────────────────────────────────────────────
PASO 1 — GRABA TU CLASE
──────────────────────────────────────────────
• Pulsa el botón rojo "🎙️ Grabar mi clase".
• Mantén silencio los primeros segundos (así la app aprende el ruido del aula).
• Cuando termines, pulsa "🛑 Detener".
• La app mejora el audio automáticamente (quita ruido y silencios).

──────────────────────────────────────────────
PASO 2 — TRANSCRIBE (la voz se vuelve texto)
──────────────────────────────────────────────
• Pulsa "📝 Transcribir" y espera.
• El texto aparecerá en la pantalla.
• Si quieres que cada frase lleve su hora, pulsa "⏱️ Con tiempos".
• Modo local = rápido y sin internet. Modo cloud = más preciso.

──────────────────────────────────────────────
PASO 3 — ANALIZA CON INTELIGENCIA ARTIFICIAL
──────────────────────────────────────────────
• Pulsa "🎓 Análisis Académico Profundo": obtienes resumen, tesis,
  ideas principales, datos importantes y registro de lo filtrado.
• Otras opciones: 📋 Resumen, 📚 Guía de estudio, 🎯 Tarjetas,
  ❓ Preguntas de examen, 🗺️ Mapa conceptual, ✨ Texto limpio, 📅 Cronología.
• Esto usa Gemini (necesita tu API Key, gratuita en aistudio.google.com/app/apikey).

──────────────────────────────────────────────
PASO 4 — GUARDA O COMPARTE
──────────────────────────────────────────────
• "📄 Guardar PDF" crea un archivo PDF de tu transcripción.
• "🌐 Google Docs" crea un documento en tu Google Drive.
• Todo se guarda solo en tu carpeta: ~/AudioClass_Recordings

──────────────────────────────────────────────
MODO FÁCIL (recomendado)
──────────────────────────────────────────────
• Activa el interruptor verde "MODO FÁCIL" arriba.
• Grabas → Detienes → la app hace TODO sola (procesa, transcribe y analiza).

CONSEJOS:
• La primera vez, Whisper descarga un modelo pequeño (tardará unos minutos).
• Puedes cambiar perfil de audio, modelo y más en "⚙️ Configuración".
• Si algo falla, pulsa "Cancelar" y vuelve a intentarlo.
"""
        box.insert("1.0", guia)
        self._guide_top = top
        self._guide_box = box
        # Localizar cada seccion por estructura (las barras de 46 guiones),
        # sin duplicar el texto de las cabeceras: asi las posiciones nunca
        # pueden desincronizarse del contenido de la guia.
        # Ojo: cada seccion tiene DOS barras (una encima y otra debajo de la
        # cabecera), asi que tras registrar la cabecera hay que saltar tambien
        # la barra de cierre para no desincronizarse con la seccion siguiente.
        barra = "─" * 46
        self._guide_sections = {}
        pos = 0
        for paso in (1, 2, 3, 4):
            k = guia.find(barra, pos)          # barra superior de la seccion
            if k < 0:
                break
            nl = guia.find("\n", k)
            if nl < 0:
                break
            # La cabecera del paso es la linea inmediatamente despues de la barra
            self._guide_sections[paso] = guia[: nl + 1].count("\n") + 1
            pos = guia.find("\n", nl + 1)      # fin de la linea de la cabecera
            if pos < 0:
                break
            pos = guia.find(barra, pos + 1)    # barra inferior que cierra la seccion
            if pos < 0:
                break
            pos = guia.find("\n", pos) + 1     # despues de la barra inferior
        self._guide_total = guia.count("\n") + 1
        try:
            box.tag_config("sec", background=C["card"], foreground=C["ok"],
                           font=("Segoe UI", 12, "bold"))
        except Exception:
            pass
        box.configure(state="disabled")

        self._btn(top, "Entendido ✓", top.destroy, width=200, height=40, fg_color=C["ok"],
                  hover_color=C["ok"]).pack(pady=(0, 18))

        if step is not None:
            self._jump_guide(step)

    def _jump_guide(self, paso):
        """Desplaza la ventana de ayuda a la seccion del paso indicado
        y resalta su cabecera en verde."""
        try:
            box = self._guide_box
            line = getattr(self, "_guide_sections", {}).get(paso)
            if box is None or not line:
                return
            total = max(getattr(self, "_guide_total", 1), 1)
            try:
                box.tag_remove("sec", "1.0", "end")
                box.tag_add("sec", f"{line}.0", f"{line}.0 lineend")
            except Exception:
                pass
            try:
                box.see(f"{line}.0")
            except Exception:
                try:
                    box.yview("moveto", max(0.0, min(1.0, (line - 2) / total)))
                except Exception:
                    pass
        except Exception:
            pass

    def _theme(self):
        self.dark = not self.dark
        self.config["theme"] = "dark" if self.dark else "light"
        save_config(self.config)
        self._apply_palette()
        try:
            self.btheme.configure(text="Oscuro" if not self.dark else "Claro")
        except Exception:
            pass
        if getattr(self, "btheme_hd", None):
            try:
                self.btheme_hd.configure(text="☀️" if not self.dark else "🌙")
            except Exception:
                pass

    def _apply_palette(self):
        """Cambia la paleta activa (claro/oscuro) y re-mapea las superficies
        registradas en _themeable, los textos, las barras doradas y el canvas."""
        C.clear(); C.update(PALETTES["dark" if self.dark else "light"])
        if CTK: ctk.set_appearance_mode("dark" if self.dark else "light")
        for kind, w, key in list(getattr(self, "_themeable", [])):
            try:
                if not w.winfo_exists() or not key:
                    continue
                newval = C.get(key)
                if not newval:
                    continue
                if kind == "frame":
                    if CTK: w.configure(fg_color=newval)
                    else: w.configure(bg=newval)
                elif kind == "btn":
                    # Los botones ademas actualizan el texto de contraste
                    # (WCAG AA) y el disabled (muted de paleta) al cambiar de tema.
                    tcol = _btn_text_color(newval)
                    if CTK:
                        w.configure(fg_color=newval, text_color=tcol,
                                    text_color_disabled=C["muted"])
                    else:
                        w.configure(bg=newval, fg=tcol)
                else:
                    if CTK: w.configure(text_color=newval)
                    else: w.configure(fg=newval)
            except Exception:
                pass
        try:
            if hasattr(self, "txt"):
                self.txt.configure(bg=C["bg"], fg=C["text"])
                # Tags del editor: el resaltado dorado en vivo y los
                # encabezados deben seguir la paleta activa al cambiar de tema.
                self.txt.tag_configure("live", foreground=C["accent"])
                self.txt.tag_configure("head", foreground=C["accent"], font=(self.FM, 11, "bold"))
            if hasattr(self, "txt_gutter"):
                self.txt_gutter.configure(bg=C["card"], fg=C["muted"])
            if hasattr(self, "vsb"):
                self.vsb.configure(bg=C["border"], troughcolor=C["bg"])
            if hasattr(self, "goldline"):
                if CTK: self.goldline.configure(fg_color=C["accent"])
                else: self.goldline.configure(bg=C["accent"])
            if hasattr(self, "easy_switch"):
                if CTK: self.easy_switch.configure(progress_color=C["easy"], button_color=C["easy"])
                else: self.easy_switch.configure(bg=C["card"], fg=C["text"])
            if hasattr(self, "easy_menu"):
                if CTK:
                    try:
                        self.easy_menu.configure(fg_color=C["button"], text_color=C["text"],
                                                 button_color=C["accent"], dropdown_fg_color=C["card"],
                                                 dropdown_hover_color=C["border"], dropdown_text_color=C["text"])
                    except Exception:
                        pass
            # Pills de pasos: re-colorear segun el paso actual (el remapeo por
            # clave no cubre estos CTkLabel crudos creados fuera de _lbl).
            if getattr(self, "_cur_step", None) is not None and getattr(self, "step_lbls", None):
                self._set_step(self._cur_step)
            # Historial: el re-mapeo resetea el fg_color de los botones al
            # default de paleta; restaurar el highlight de la seleccion activa.
            if getattr(self, "sel", None) is not None and hasattr(self, "hist_frame"):
                self._selhist(self.sel)
            if hasattr(self, "adapt_txt"):
                if CTK: self.adapt_txt.configure(fg_color=C["bg"], text_color=C["text"])
                else: self.adapt_txt.configure(bg=C["bg"], fg=C["text"])
            for pbar in getattr(self, "_gold_bars", []):
                try:
                    pbar.configure(progress_color=C["accent"], fg_color=C["button"])
                except Exception:
                    pass
            # Historico del VU meter: re-pintar con la paleta activa
            if hasattr(self, "vu_hist"):
                try:
                    self.vu_hist.configure(bg=C["card"], highlightbackground=C["border"])
                    self._draw_vu_hist()
                except Exception:
                    pass
            if hasattr(self, "vu_sens_slider") and CTK:
                try:
                    self.vu_sens_slider.configure(progress_color=C["accent"], button_color=C["accent"])
                except Exception:
                    pass
            if hasattr(self, "fig"):
                self.fig.set_facecolor(C["card"])
                self.ax.set_facecolor(C["card"])
                for sp in self.ax.spines.values():
                    sp.set_color(C["border"])
                self.line.set_color(C["accent"])
                self.canvas.draw_idle()
            if CTK: self.configure(fg_color=C["bg"])
            else: self.configure(bg=C["bg"])
        except Exception:
            pass

    def _test_adapt(self, entry, model_var, provider="gemini"):
        """Prueba la API Key de un proveedor (gemini/openai) desde configuracion (asincrono)."""
        is_gemini = provider == "gemini"
        lbl_attr = "gemini_test_lbl" if is_gemini else "openai_test_lbl"
        btn_attr = "btn_test_gemini" if is_gemini else "btn_test_openai"
        prov_label = "Gemini" if is_gemini else "OpenAI"
        try:
            # El dialogo pudo haberse cerrado (auto-test con after): no tocar widgets destruidos
            if not (hasattr(self, lbl_attr) and getattr(self, lbl_attr).winfo_exists()):
                return
            key = entry.get().strip()
            model = model_var.get()  # leer en el hilo principal, nunca dentro del worker
        except Exception:
            return

        if len(key) < 10:
            getattr(self, lbl_attr).configure(text="Introduce una API Key primero", text_color=C["warn"])
            return
        if hasattr(self, btn_attr) and getattr(self, btn_attr).winfo_exists():
            getattr(self, btn_attr).configure(state="disabled", text="Probando...")
        getattr(self, lbl_attr).configure(text=f"Probando conexión con {prov_label}...", text_color=C["warn"])

        def worker():
            try:
                if is_gemini:
                    engine = GeminiAdaptationEngine(key, model)
                else:
                    engine = OpenAIAdaptationEngine(key, model)
                self.q.put(("adapt_test", (provider, engine.test_key())))
            except Exception as e:
                self.q.put(("adapt_test", (provider, (False, f"Error inesperado: {e}"))))

        threading.Thread(target=worker, daemon=True).start()

    def _connect_google(self, creds_path):
        """Conecta con Google Docs (OAuth) desde la ventana de configuracion."""
        try:
            if not (hasattr(self, "gdoc_lbl") and self.gdoc_lbl.winfo_exists()):
                return
            path = (creds_path or "").strip()
        except Exception:
            return

        if not path or not os.path.exists(path):
            self.gdoc_lbl.configure(text="Selecciona primero tu archivo client_secret.json", text_color=C["err"])
            return

        self.config["google_creds_path"] = path
        save_config(self.config)
        self.docs_exporter = GoogleDocsExporter(path)

        if hasattr(self, "btn_gdoc_connect") and self.btn_gdoc_connect.winfo_exists():
            self.btn_gdoc_connect.configure(state="disabled", text="Conectando...")
        self.gdoc_lbl.configure(text="Abriendo el navegador para autorizar...", text_color=C["warn"])

        def worker():
            try:
                ok = self.docs_exporter.connect()
                msg = "Conectado a Google Docs" if ok else (self.docs_exporter.error or "Error de conexion")
                self.q.put(("gdoc_connect", (ok, msg)))
            except Exception as e:
                self.q.put(("gdoc_connect", (False, f"Error inesperado: {e}")))

        threading.Thread(target=worker, daemon=True).start()

    def _export_docs(self):
        """Exporta la transcripcion (o la adaptacion) actual a Google Docs."""
        if not _gdocs_importable():
            self._msg("warning", "Google Docs",
                      "La exportación a Google Docs no está disponible en esta versión: "
                      "el componente google-auth-oauthlib no está incluido en el instalador.\n\n"
                      "Puedes seguir usando PDF, DOCX o copiar el texto.\n"
                      "Para activarla (solo usuarios avanzados):\n"
                      "  pip install google-auth-oauthlib google-api-python-client")
            return
        if not self.last_text:
            self._msg("warning", "Sin contenido", "Primero transcribe o adapta una clase.")
            return

        if not self.docs_exporter.is_configured():
            self._msg("warning", "Google Docs", "Configura tus credenciales en Configuracion (seccion Google Docs) y pulsa Conectar.")
            return

        # El worker de export() valida y refresca el token; aqui solo evitamos el caso evidente
        if not os.path.exists(self.docs_exporter.token_path):
            self._msg("warning", "Google Docs", "Conecta con Google primero (Configuracion > Google Docs > Conectar con Google).")
            return

        # Preguntar que exportar: transcripcion o adaptacion (si existe)
        adapt_text = ""
        try:
            adapt_text = self.adapt_txt.get("1.0", "end").strip()
        except Exception:
            pass

        content = ("Transcripción automática — puede contener errores. No constituye acta oficial.\n\n"
                   + self.last_text)
        kind = "Transcripcion"
        if adapt_text:
            if self._ask("Exportar a Google Docs",
                         "Exportar la ADAPTACION (Analisis/Resumen)?\n\nSi = adaptacion\nNo = transcripcion en bruto"):
                content = adapt_text
                kind = "Adaptacion"

        base = os.path.splitext(os.path.basename(self.last_path))[0] if self.last_path else "clase"
        title = f"{base} - {kind} - AudioClass"

        self.bdocs.configure(state="disabled", text="Exportando...")
        self.lstatus.configure(text="Exportando a Google Docs...", text_color=C["ok"])

        def worker():
            res = self.docs_exporter.export(title, content)
            if "error" in res:
                self.q.put(("gdoc_done", (False, res["error"])))
            else:
                self.q.put(("gdoc_done", (True, res.get("url", ""))))

        threading.Thread(target=worker, daemon=True).start()

    def _open_output_dir(self):
        """Abre la carpeta de grabaciones en el explorador de archivos."""
        try:
            if sys.platform == "win32":
                os.startfile(OUTPUT_DIR)
            elif sys.platform == "darwin":
                subprocess.call(["open", OUTPUT_DIR])
            else:
                subprocess.call(["xdg-open", OUTPUT_DIR])
        except Exception as e:
            self._msg("error", "Error", f"No se pudo abrir la carpeta:\n{e}")

    def _test_mic(self):
        """Ventana de prueba nativa del microfono: graba ~8 s con el pipeline
        activo, muestra un medidor de nivel en vivo y las metricas de calidad
        (adaptacion de grabar_prueba.py integrada en la app)."""
        # Si la ventana ya esta abierta, reutilizarla (evitar duplicados)
        if getattr(self, "mic_test_top", None) is not None:
            try:
                if self.mic_test_top.winfo_exists():
                    self.mic_test_top.lift()
                    self.mic_test_top.focus_force()
                    return
            except Exception:
                pass

        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("🎤 Prueba de Microfono")
        top.geometry("600x440")
        top.transient(self)
        top.grab_set()
        self.mic_test_top = top
        self._mic_busy = False

        self._lbl(top, "🎤 Prueba rapida de microfono", font=("Segoe UI", 18, "bold"),
                  text_color=C["accent"]).pack(pady=(18, 4))
        self._lbl(top, "Pulsa el boton, espera 2 segundos y habla durante ~6 segundos.",
                  font=("Segoe UI", 12), text_color=C["muted"]).pack(pady=(0, 12))

        lvl_row = self._frame(top, fg_color="transparent")
        lvl_row.pack(fill="x", padx=30, pady=(0, 4))
        self._lbl(lvl_row, "Nivel:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        if CTK:
            self.mic_lvl_bar = ctk.CTkProgressBar(lvl_row, height=14, corner_radius=7,
                                                  progress_color=C["muted"])
        else:
            self.mic_lvl_bar = ttk.Progressbar(lvl_row, mode="determinate", maximum=100)
        self.mic_lvl_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.mic_lvl_lbl = self._lbl(lvl_row, "-∞ dB", font=("Segoe UI", 10), text_color=C["muted"])
        self.mic_lvl_lbl.pack(side="left")

        self.mic_state = self._lbl(top, "", font=("Segoe UI", 12), text_color=C["warn"])
        self.mic_state.pack(pady=(8, 4))

        self.mic_result = self._lbl(top, "", font=("Segoe UI", 11), text_color=C["text"],
                                    anchor="w", wraplength=540)
        self.mic_result.pack(padx=30, pady=(4, 10))

        self.btn_mic_test = self._btn(top, "🎙️ Comenzar prueba (8 s)", self._mic_test_start,
                                      width=280, height=44, font=("Segoe UI", 14, "bold"),                                       fg_color=C["err"], hover_color=C["err"])
        self.btn_mic_test.pack(pady=(4, 8))
        self._btn(top, "Cerrar", top.destroy, width=140, height=36).pack(pady=(0, 14))

    def _mic_test_start(self):
        """Arranca la grabacion de prueba en un hilo (sin bloquear la UI)."""
        try:
            if getattr(self, "_mic_busy", False):
                return
            self._mic_busy = True
            if hasattr(self, "btn_mic_test") and self.btn_mic_test.winfo_exists():
                self.btn_mic_test.configure(state="disabled", text="Escuchando... habla ahora")
            if hasattr(self, "mic_state") and self.mic_state.winfo_exists():
                self.mic_state.configure(text="🎙️ HABLA AHORA durante ~6 segundos", text_color=C["err"])
            if hasattr(self, "mic_result") and self.mic_result.winfo_exists():
                self.mic_result.configure(text="")
            threading.Thread(target=self._mic_test_worker, daemon=True).start()
        except Exception:
            self._mic_busy = False

    def _mic_test_worker(self):
        """Graba ~8 s con el microfono, procesa con el pipeline activo y
        envia las metricas a la UI por la cola (no tocar widgets desde el hilo)."""
        try:
            SR = SAMPLE_RATE
            DUR = 8
            win = int(0.1 * SR)
            buf = []

            def cb(indata, frames, ti, status):
                x = indata.copy().flatten()
                buf.append(x)
                r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if len(x) else 0.0
                self.q.put(("mic_lvl", r))

            with sd.InputStream(samplerate=SR, channels=1, dtype=np.float32,
                                blocksize=win, callback=cb):
                t0 = time.time()
                while time.time() - t0 < DUR:
                    time.sleep(0.05)

            if not buf:
                self.q.put(("mic_result", "No se capturo audio del microfono."))
                return
            raw = np.concatenate(buf).flatten()
            proc = self.pipeline.process(raw)
            self.q.put(("mic_result", self._mic_metrics(raw, proc)))
        except Exception as e:
            self.q.put(("mic_result", f"Error: {e}"))
        finally:
            self._mic_busy = False
            self.q.put(("mic_idle", None))

    def _mic_metrics(self, raw, proc):
        """Metricas objetivas raw vs mejorado (en memoria, sin guardar WAVs)."""
        SR = SAMPLE_RATE
        w = int(0.04 * SR)
        hop = w // 2
        fr_r = self.pipeline._frame_rms(raw.astype(np.float64), w, hop)
        fr_p = self.pipeline._frame_rms(proc.astype(np.float64), w, hop)
        if len(fr_r) == 0 or len(fr_p) == 0:
            return "Audio demasiado corto para analizar."
        floor_r = float(np.percentile(fr_r, 10))
        floor_p = float(np.percentile(fr_p, 10))
        speech_r = float(np.percentile(fr_r, 90))
        speech_p = float(np.percentile(fr_p, 90))
        QUIET = 0.01
        sil_r = float(np.mean(fr_r < QUIET)) * 100
        sil_p = float(np.mean(fr_p < QUIET)) * 100

        def band(x, lo, hi):
            if len(x) < 512:
                return 0.0
            f, P = signal.welch(x, fs=SR, nperseg=2048)
            return float(np.sum(P[(f >= lo) & (f <= hi)]))

        vi, vo = band(raw, 200, 3000), band(proc, 200, 3000)
        hii, hoo = band(raw, 7100, 7900), band(proc, 7100, 7900)
        pk = float(np.max(np.abs(proc))) if len(proc) else 0.0
        snr = speech_p / max(floor_p, 1e-12)
        lines = []
        if speech_p > 0.02:
            lines.append(f"✓ Voz detectada (nivel de habla {speech_p:.3f})")
        else:
            lines.append(f"⚠️ Voz muy baja ({speech_p:.3f}) — acercate al microfono o habla mas alto")
        lines.append(f"Silencio recortado: {sil_r:.0f}% -> {sil_p:.0f}% (noise gate)")
        lines.append(f"Nivel de habla: {speech_r:.4f} -> {speech_p:.4f}")
        lines.append(f"SNR habla/piso: {snr:.1f}x")
        lines.append(f"Voz 200-3000 Hz: x{vo / max(vi, 1e-12):.2f}")
        # Evitar '-inf dB' si el filtro paso-bajas deja la banda alta en cero
        # (silencio digital o perfil con lp_freq bajo): se reporta 'sin señal'.
        if hoo <= 1e-12:
            lines.append("Agudos 7.1-7.9 kHz: sin señal (filtrado por el perfil)")
        else:
            lines.append(f"Agudos 7.1-7.9 kHz: {20 * np.log10(hoo / max(hii, 1e-12)):+.1f} dB")
        lines.append(f"Pico: {pk:.3f} (limite {self.pipeline.p['limiter']:.2f}, sin clipping)")
        return "\n".join(lines)

    # ── Optimizador de microfono (integrado, sin salir de la app) ──────────
    def _open_mic_opt(self):
        """Ventana del optimizador de microfono: diagnostica el nivel de
        entrada, el permiso de privacidad y todos los microfonos, y puede
        aplicar la correccion (nivel 100% + desmute + boost) SIN salir de la
        app. Reutiliza las funciones CoreAudio de optimizar_mic.py (ctypes)."""
        if getattr(self, "mic_opt_top", None) is not None:
            try:
                if self.mic_opt_top.winfo_exists():
                    self.mic_opt_top.lift()
                    self.mic_opt_top.focus_force()
                    return
            except Exception:
                pass

        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("🎛️ Optimizador de micrófono")
        top.geometry("680x560")
        top.transient(self)
        top.grab_set()
        self.mic_opt_top = top

        self._lbl(top, "🎛️ Optimizador de micrófono", font=("Segoe UI", 18, "bold"),
                  text_color=C["accent"]).pack(pady=(16, 4))
        self._lbl(top, "Diagnostica el nivel de entrada y corrige las grabaciones en silencio. "
                       "Habla en voz alta durante cada prueba de 4 segundos.",
                  font=("Segoe UI", 11), text_color=C["muted"], wraplength=620).pack(pady=(0, 10))

        lvl_row = self._frame(top, fg_color="transparent")
        lvl_row.pack(fill="x", padx=30, pady=(0, 4))
        self._lbl(lvl_row, "Nivel:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        if CTK:
            self.mic_opt_lvl_bar = ctk.CTkProgressBar(lvl_row, height=14, corner_radius=7,
                                                      progress_color=C["muted"])
        else:
            self.mic_opt_lvl_bar = ttk.Progressbar(lvl_row, mode="determinate", maximum=100)
        self.mic_opt_lvl_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.mic_opt_lvl_lbl = self._lbl(lvl_row, "-∞ dB", font=("Segoe UI", 10), text_color=C["muted"])
        self.mic_opt_lvl_lbl.pack(side="left")

        self.mic_opt_state_lbl = self._lbl(top, "", font=("Segoe UI", 12), text_color=C["warn"])
        self.mic_opt_state_lbl.pack(pady=(6, 4))

        if CTK:
            self.mic_opt_txt = ctk.CTkTextbox(top, height=250, font=("Consolas", 10),
                                              text_color=C["text"], fg_color=C["card"],
                                              border_width=1, border_color=C["border"],
                                              wrap="word", state="disabled")
        else:
            self.mic_opt_txt = tk.Text(top, height=16, font=("Consolas", 10),
                                       bg=C["card"], fg=C["text"], wrap="word",
                                       state="disabled", relief="flat", borderwidth=1,
                                       highlightthickness=1, highlightbackground=C["border"])
        self.mic_opt_txt.pack(fill="both", expand=True, padx=30, pady=(4, 8))

        btns = self._frame(top, fg_color="transparent")
        btns.pack(fill="x", padx=30, pady=(0, 14))
        self.btn_mic_opt_diag = self._btn(btns, "🔍 Diagnosticar", lambda: self._mic_opt_start(False),
                                          width=200, height=40, font=("Segoe UI", 12, "bold"),
                                          fg_color=C["accent"], hover_color=C["accent_hover"])
        self.btn_mic_opt_diag.pack(side="left", padx=(0, 8))
        self.btn_mic_opt_apply = self._btn(btns, "⚡ Aplicar optimización", lambda: self._mic_opt_start(True),
                                           width=225, height=40, font=("Segoe UI", 12, "bold"),
                                           fg_color=C["ok"], hover_color=C["ok"])
        self.btn_mic_opt_apply.pack(side="left", padx=(0, 8))
        self._btn(btns, "Cerrar", top.destroy, width=100, height=36).pack(side="left")

    def _mic_opt_start(self, do_apply):
        """Arranca el diagnostico/optimizacion en un hilo (no bloquea la UI)."""
        try:
            if getattr(self, "_mic_opt_busy", False):
                return
            self._mic_opt_busy = True
            for b in ("btn_mic_opt_diag", "btn_mic_opt_apply"):
                w = getattr(self, b, None)
                if w is not None:
                    try:
                        if w.winfo_exists():
                            w.configure(state="disabled")
                    except Exception:
                        pass
            if hasattr(self, "mic_opt_txt"):
                try:
                    self.mic_opt_txt.configure(state="normal")
                    self.mic_opt_txt.delete("1.0", "end")
                    self.mic_opt_txt.configure(state="disabled")
                except Exception:
                    pass
            threading.Thread(target=self._mic_opt_worker, args=(do_apply,), daemon=True).start()
        except Exception:
            self._mic_opt_busy = False

    def _mic_opt_worker(self, do_apply):
        """Hilo del optimizador: diagnostica (dispositivo, nivel, mute, permiso,
        todos los mics) y, si do_apply, aplica 100% + desmute + boost. Los
        avances van por la cola (_poll) para no tocar widgets desde el hilo."""
        try:
            if sys.platform != "win32":
                self.q.put(("mic_opt_log", "El optimizador solo aplica en Windows.\n"))
                self.q.put(("mic_opt_done", "NO_WINDOWS"))
                return
            import optimizar_mic as om
            log = self.q.put

            log(("mic_opt_log", "Leyendo dispositivo por defecto...\n"))
            dev = om._default_capture_device()
            did = om._device_id(dev)
            sname = "?"
            try:
                sname = sd.query_devices(sd.default.device[0])["name"]
            except Exception:
                pass
            log(("mic_opt_log", f"Dispositivo por defecto: {sname}\n"))
            st = om.get_mic_state(dev)
            if st:
                log(("mic_opt_log", f"  Nivel: {st[0]}%  |  Mute: {'SÍ ⚠️' if st[1] else 'No'}\n"))
            else:
                log(("mic_opt_log", "  (nivel no accesible)\n"))

            pv = om.privacy_mic()
            if pv != "Allow":
                log(("mic_opt_log", f"Permiso de micrófono: {pv}  ⚠️ DENEGADO — permite el acceso en "
                                     "Configuración > Privacidad > Micrófono\n"))
            else:
                log(("mic_opt_log", "Permiso de micrófono: Allow\n"))

            log(("mic_opt_log", "Microfonos activos:\n"))
            try:
                for did2, lvl, mute in om.list_mics():
                    mark = " [DEFAULT]" if did2 == did else ""
                    extra = f"nivel {lvl}%" + (" mute ⚠️" if mute else "")
                    log(("mic_opt_log", f"  {extra}{mark}  {did2[:64]}\n"))
            except Exception as e:
                log(("mic_opt_log", f"  (no enumerable: {e})\n"))

            # Prueba de señal ANTES (piso/p90/peak) con medidor en vivo
            self.q.put(("mic_opt_state", "🎙️ HABLA AHORA durante 4 s"))
            antes = om.measure_signal(4.0, on_level=lambda r: self.q.put(("mic_opt_lvl", r)))
            self.q.put(("mic_opt_state", ""))
            log(("mic_opt_log", f"Prueba: {antes['dur']:.1f}s | piso {antes['piso']:.4f} | "
                                 f"p90 {antes['p90']:.4f} | peak {antes['peak']:.3f} → {antes['veredicto']}\n"))
            if not do_apply:
                if antes["veredicto"] == "OK":
                    log(("mic_opt_log", "✅ El micrófono captura bien. No se requiere optimización.\n"))
                else:
                    log(("mic_opt_log", "Sugerencia: pulsa '⚡ Aplicar optimización' para subir el nivel "
                                         "al 100% y activar el boost si el driver lo permite.\n"))
                self.q.put(("mic_opt_done", antes["veredicto"]))
                return

            # ── Aplicar optimizacion ────────────────────────────────────────
            log(("mic_opt_log", "\nAPLICANDO OPTIMIZACIÓN...\n"))
            ok1, err1 = om.apply_mic_level(dev, 100)
            log(("mic_opt_log", f"  [{'OK' if ok1 else 'NO'}] nivel → 100% + desmute  {err1}\n"))
            ok2, msg2 = om.apply_boost(dev)
            log(("mic_opt_log", f"  [{'OK' if ok2 else 'NO'}] boost del nodo de volumen  {msg2}\n"))
            time.sleep(0.5)
            st2 = om.get_mic_state(dev)
            if st2:
                log(("mic_opt_log", f"  Estado tras aplicar: nivel {st2[0]}% | mute {'SÍ ⚠️' if st2[1] else 'No'}\n"))

            self.q.put(("mic_opt_state", "🎙️ HABLA AHORA durante 4 s (post-optimización)"))
            despues = om.measure_signal(4.0, on_level=lambda r: self.q.put(("mic_opt_lvl", r)))
            self.q.put(("mic_opt_state", ""))
            log(("mic_opt_log", f"Post: {despues['dur']:.1f}s | piso {despues['piso']:.4f} | "
                                 f"p90 {despues['p90']:.4f} | peak {despues['peak']:.3f} → {despues['veredicto']}\n"))
            mejo = despues["p90"] / max(antes["p90"], 1e-6)
            log(("mic_opt_log", f"RESUMEN: p90 {antes['p90']:.4f} → {despues['p90']:.4f}  (x{mejo:.1f})\n"))
            if despues["veredicto"] == "OK":
                log(("mic_opt_log", "✅ El micrófono quedó optimizado. La app ya capturará tu voz.\n"))
            elif despues["veredicto"] == "DÉBIL":
                log(("mic_opt_log", "⚠️ Sigue débil. Si NO hablaste en la prueba, repítela hablando. Si hablaste "
                                     "y sigue débil: acércate al micro, revisa el boost en Realtek Audio Console "
                                     "o desactiva la supresión de ruido agresiva.\n"))
            else:
                log(("mic_opt_log", "❌ Sigue sin señal: revisa que el micro no esté físicamente desactivado "
                                     "y que el dispositivo por defecto sea el correcto.\n"))
            self.q.put(("mic_opt_done", despues["veredicto"]))
        except Exception as e:
            log_exc("mic optimizer")
            try:
                self.q.put(("mic_opt_log", f"Error: {str(e)[:120]}\n"))
            except Exception:
                pass
            self.q.put(("mic_opt_done", "ERROR"))

    def _open_config(self):
        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("Configuracion de AudioClass")
        top.geometry("650x1060")
        top.transient(self)
        top.grab_set()

        f1 = self._frame(top, fg_color=C["card"])
        f1.pack(fill="x", padx=20, pady=10)
        self._lbl(f1, "🤖 Proveedor de IA para el análisis", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f1, "Elige con qué servicio analizar tus clases (resúmenes, guías, exámenes):",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 8))
        adapt_provider = ctk.StringVar(value=self.config.get("adapt_provider", "gemini"))
        prov_row = self._frame(f1, fg_color="transparent")
        prov_row.pack(anchor="w", padx=15, pady=(0, 8))
        for val, lbl in (("gemini", "✨ Gemini (Google)"), ("openai", "🤖 OpenAI (GPT)")):
            rb = ctk.CTkRadioButton(prov_row, text=lbl, variable=adapt_provider, value=val,
                                    font=("Segoe UI", 11), text_color=C["text"])
            rb.pack(side="left", padx=(0, 25))
            self._themeable.append(("label", rb, "text"))

        # ── Sección Gemini ──
        f1g = self._frame(f1, fg_color="transparent")
        f1g.pack(fill="x", padx=15, pady=(0, 8))
        self._lbl(f1g, "API Key de Google AI Studio (Gemini)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 2))
        self._lbl(f1g, "Consiguela gratis en: aistudio.google.com/app/apikey", font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", pady=(0, 4))
        gemini_entry = self._entry(f1g, width=500, font=("Segoe UI", 11))
        gemini_entry.pack(anchor="w", pady=(0, 4))
        gemini_entry.insert(0, self.config.get("gemini_api_key", ""))

        gemini_model = ctk.StringVar(value=self.config.get("gemini_model", "flash"))
        gmod_row = self._frame(f1g, fg_color="transparent")
        gmod_row.pack(anchor="w", pady=(0, 4))
        if CTK:
            # Radiobuttons en vez de segmented: el texto unico del segmented no
            # cumple contraste en ambos estados (activo=acento / inactivo=gris).
            for val, lbl in (("flash", "Flash"), ("pro", "Pro")):
                rb = ctk.CTkRadioButton(gmod_row, text=lbl, variable=gemini_model, value=val,
                                        font=("Segoe UI", 11), text_color=C["text"])
                rb.pack(side="left", padx=(0, 20))
                self._themeable.append(("label", rb, "text"))
        else:
            ctk.OptionMenu(f1g, gemini_model, "flash", "pro").pack(anchor="w", padx=15, pady=(0, 12))
        self._lbl(f1g, "flash = rapido y economico (Gemini 2.0 Flash) | pro = maxima calidad (Gemini 2.5 Pro)",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", pady=(0, 4))

        test_row = self._frame(f1g, fg_color="transparent")
        test_row.pack(fill="x", pady=(0, 4))
        self.gemini_test_lbl = self._lbl(test_row, "", font=("Segoe UI", 10), text_color=C["muted"])
        self.gemini_test_lbl.pack(side="left", padx=(0, 10))
        self.btn_test_gemini = self._btn(test_row, "Probar Conexión",
                                         lambda: self._test_adapt(gemini_entry, gemini_model, "gemini"),
                                         width=150, height=30, fg_color=C["accent"])
        self.btn_test_gemini.pack(side="left")

        # ── Sección OpenAI ──
        f1o = self._frame(f1, fg_color="transparent")
        f1o.pack(fill="x", padx=15, pady=(0, 8))
        self._lbl(f1o, "API Key de OpenAI (GPT)", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 2))
        self._lbl(f1o, "Consiguela en: platform.openai.com/api-keys (tiene plan gratuito inicial)",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", pady=(0, 4))
        openai_entry = self._entry(f1o, width=500, font=("Segoe UI", 11))
        openai_entry.pack(anchor="w", pady=(0, 4))
        openai_entry.insert(0, self.config.get("openai_api_key", ""))

        openai_model = ctk.StringVar(value=self.config.get("openai_model", "mini"))
        omod_row = self._frame(f1o, fg_color="transparent")
        omod_row.pack(anchor="w", pady=(0, 4))
        for val, lbl in (("mini", "GPT-4o mini"), ("gpt4o", "GPT-4o")):
            rb = ctk.CTkRadioButton(omod_row, text=lbl, variable=openai_model, value=val,
                                    font=("Segoe UI", 11), text_color=C["text"])
            rb.pack(side="left", padx=(0, 20))
            self._themeable.append(("label", rb, "text"))
        self._lbl(f1o, "mini = rapido y economico | GPT-4o = maxima calidad",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", pady=(0, 4))

        otest_row = self._frame(f1o, fg_color="transparent")
        otest_row.pack(fill="x", pady=(0, 4))
        self.openai_test_lbl = self._lbl(otest_row, "", font=("Segoe UI", 10), text_color=C["muted"])
        self.openai_test_lbl.pack(side="left", padx=(0, 10))
        self.btn_test_openai = self._btn(otest_row, "Probar Conexión",
                                         lambda: self._test_adapt(openai_entry, openai_model, "openai"),
                                         width=150, height=30, fg_color=C["accent"])
        self.btn_test_openai.pack(side="left")

        # Auto-test solo del proveedor activo al abrir la ventana
        if self.config.get("adapt_provider", "gemini") == "openai":
            if self.config.get("openai_api_key"):
                self.after(400, lambda: self._test_adapt(openai_entry, openai_model, "openai"))
        elif self.config.get("gemini_api_key"):
            self.after(400, lambda: self._test_adapt(gemini_entry, gemini_model, "gemini"))

        f2 = self._frame(top, fg_color=C["card"])
        f2.pack(fill="x", padx=20, pady=10)
        self._lbl(f2, "Google Colab (Cloud GPU)", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f2, "URL de ngrok desde tu servidor de Colab:", font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 8))
        colab_entry = self._entry(f2, width=500, font=("Segoe UI", 11))
        colab_entry.pack(anchor="w", padx=15, pady=(0, 8))
        colab_entry.insert(0, self.config.get("colab_url", ""))

        colab_key = self._entry(f2, width=200, font=("Segoe UI", 11))
        colab_key.pack(anchor="w", padx=15, pady=(0, 12))
        colab_key.insert(0, self.config.get("colab_key", "audioclass"))

        f0 = self._frame(top, fg_color=C["card"])
        f0.pack(fill="x", padx=20, pady=10)
        self._lbl(f0, "🎤 Prueba rapida de microfono", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f0, "Graba 8 segundos y comprueba que tu microfono capta bien tu voz.",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 8))
        self._btn(f0, "🎙️ Abrir prueba de microfono", self._test_mic, width=240, height=36,
                  fg_color=C["err"], hover_color=C["err"]).pack(anchor="w", padx=15, pady=(0, 12))

        f3 = self._frame(top, fg_color=C["card"])
        f3.pack(fill="x", padx=20, pady=10)
        self._lbl(f3, "Estado de Conexiones", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(12, 8))

        status_frame = self._frame(f3, fg_color="transparent")
        status_frame.pack(fill="x", padx=15, pady=(0, 12))

        self._lbl(status_frame, "Modelo Local:", font=("Segoe UI", 11)).pack(side="left")
        self._lbl(status_frame, "Listo" if self.local_engine.ready else "Cargando...", 
                  font=("Segoe UI", 11), text_color=C["ok"] if self.local_engine.ready else C["warn"]).pack(side="left", padx=(5, 20))

        self._lbl(status_frame, "Colab:", font=("Segoe UI", 11)).pack(side="left")
        has_url = bool(self.config.get("colab_url"))
        self._lbl(status_frame, "Configurado" if has_url else "Sin URL", 
                  font=("Segoe UI", 11), text_color=C["ok"] if has_url else C["err"]).pack(side="left", padx=(5, 20))

        self._lbl(status_frame, "Gemini:", font=("Segoe UI", 11)).pack(side="left")
        has_key = bool(self.config.get("gemini_api_key"))
        self._lbl(status_frame, "Configurado" if has_key else "Sin Key", 
                  font=("Segoe UI", 11), text_color=C["ok"] if has_key else C["err"]).pack(side="left", padx=5)

        self._lbl(status_frame, "OpenAI:", font=("Segoe UI", 11)).pack(side="left")
        has_oai = bool(self.config.get("openai_api_key"))
        self._lbl(status_frame, "Configurado" if has_oai else "Sin Key", 
                  font=("Segoe UI", 11), text_color=C["ok"] if has_oai else C["err"]).pack(side="left", padx=5)

        f4 = self._frame(top, fg_color=C["card"])
        f4.pack(fill="x", padx=20, pady=10)
        self._lbl(f4, "Google Docs (exportar transcripciones)", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f4, "1. Crea credenciales OAuth en console.cloud.google.com (tipo 'App de escritorio') y habilita la Docs API",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 2))
        self._lbl(f4, "2. Descarga el client_secret.json y seleccionalo:",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 6))

        gdoc_row = self._frame(f4, fg_color="transparent")
        gdoc_row.pack(fill="x", padx=15, pady=(0, 8))
        gdoc_entry = self._entry(gdoc_row, width=380, font=("Segoe UI", 10))
        gdoc_entry.pack(side="left", padx=(0, 6))
        gdoc_entry.insert(0, self.config.get("google_creds_path", ""))

        def _pick_creds():
            fp = filedialog.askopenfilename(title="Selecciona client_secret.json",
                                            filetypes=[("Credenciales JSON", "*.json")])
            if fp:
                gdoc_entry.delete(0, "end")
                gdoc_entry.insert(0, fp)

        self._btn(gdoc_row, "Examinar...", _pick_creds, width=100, height=30).pack(side="left", padx=(0, 10))
        self.btn_gdoc_connect = self._btn(gdoc_row, "Conectar con Google",
                                           lambda: self._connect_google(gdoc_entry.get().strip()),
                                           width=150, height=30, fg_color=C["ok"])
        self.btn_gdoc_connect.pack(side="left")

        self.gdoc_lbl = self._lbl(f4, "", font=("Segoe UI", 10))
        self.gdoc_lbl.pack(anchor="w", padx=15, pady=(0, 12))

        # Estado inicial de Google Docs (sin abrir navegador ni refrescar token en el hilo principal)
        if not _gdocs_importable():
            try:
                self.btn_gdoc_connect.configure(state="disabled")
                self.gdoc_lbl.configure(text="No disponible en esta versión: falta google-auth-oauthlib "
                                             "(no incluido en el instalador).", text_color=C["warn"])
            except Exception:
                pass
        else:
            try:
                gok, gmsg = self.docs_exporter.test_connection(refresh=False)
                self.gdoc_lbl.configure(text=("✓ " if gok else "· ") + gmsg,
                                        text_color=C["ok"] if gok else C["muted"])
            except Exception:
                pass

        # ── Privacidad / consentimiento de IA ──
        fp = self._frame(f1, fg_color="transparent")
        fp.pack(fill="x", padx=15, pady=(8, 4))
        self._lbl(fp, "🔒 Privacidad", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 2))
        self._lbl(fp, "Las transcripciones se procesan en tu equipo. El análisis con IA envía el texto a Gemini/OpenAI (retención temporal del proveedor). El contenido generado por IA puede contener errores y no es consejo médico/legal ni acta oficial.",
                  font=("Segoe UI", 10), text_color=C["muted"], wraplength=560, justify="left").pack(anchor="w", pady=(0, 4))
        ia_consent_var = ctk.BooleanVar(value=bool(self.config.get("ia_consent", False)))
        if CTK:
            ctk.CTkCheckBox(fp, text="Permito el análisis con IA (envío de mis transcripciones a Gemini/OpenAI)",
                            variable=ia_consent_var, font=("Segoe UI", 11), fg_color=C["accent"]).pack(anchor="w", pady=(0, 10))
        else:
            ctk.Checkbutton(fp, text="Permito el analisis con IA (envio a Gemini/OpenAI)", variable=ia_consent_var,
                            bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", pady=(0, 10))

        def save():
            self.config["adapt_provider"] = adapt_provider.get()
            self.config["gemini_api_key"] = gemini_entry.get().strip()
            self.config["gemini_model"] = gemini_model.get()
            self.config["openai_api_key"] = openai_entry.get().strip()
            self.config["openai_model"] = openai_model.get()
            self.config["colab_url"] = colab_entry.get().strip()
            self.config["colab_key"] = colab_key.get().strip()
            self.config["google_creds_path"] = gdoc_entry.get().strip()
            self.config["ia_consent"] = bool(ia_consent_var.get())
            save_config(self.config)

            self.adapt_engine = self._build_adapt_engine()
            self.cloud_engine = CloudColabEngine(
                self.config["colab_url"], self.config["colab_key"],
                self.config.get("whisper_language", "auto")
            )
            self.docs_exporter = GoogleDocsExporter(
                self.config["google_creds_path"]
            )
            self._update_adapt_status()
            self._chmode(self.mode_var.get())  # ya refresca el resumen de configuracion
            top.destroy()
            self._msg("info", "Guardado", "Configuracion actualizada correctamente.")

        self._btn(top, "Guardar Cambios", save, width=200, height=40, 
                  fg_color=C["accent"]).pack(pady=20)

    def _loadhist(self):
        try:
            files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.endswith("_mejorado.wav")], reverse=True)[:30]
            for f in files:
                self._addhist(os.path.join(OUTPUT_DIR, f))
        except: pass

    def _addhist(self, path):
        if path in [h["path"] for h in self.history]: return
        name = os.path.basename(path).replace("_mejorado.wav", "")
        self.history.append({"path": path, "name": name})
        if CTK:
            b = ctk.CTkButton(self.hist_frame, text="🗂  " + name, anchor="w", font=(self.FB, 11),
                               height=36, corner_radius=8, fg_color=C["button"],
                               text_color=C["text"],
                               hover_color=C["border"], border_width=1, border_color=C["border"],
                               command=lambda p=path: self._selhist(p))
            b.pack(fill="x", pady=(0, 4), padx=2)
            b._path = path
            self._themeable.append(("btn", b, "button"))
        else:
            b = ctk.Button(self.hist_frame, text=name, anchor="w", font=("Segoe UI", 11),
                            bg=C["card"], fg=C["text"], command=lambda p=path: self._selhist(p))
            b.pack(fill="x", pady=(0, 4))
            b._path = path

    def _selhist(self, path):
        self.sel = path
        for btn in ("bplay", "btransh", "bdel", "bcompile"):
            b = getattr(self, btn, None)
            if b is not None:
                try:
                    b.configure(state="normal" if btn != "bcompile" or self.compile_buffer else "disabled")
                except Exception:
                    pass
        for c in self.hist_frame.winfo_children():
            if hasattr(c, '_path'):
                col = C["accent"] if c._path == path else (C["button"] if CTK else C["card"])
                if CTK: c.configure(fg_color=col)
                else: c.config(bg=col)

    def _play(self):
        if not self.sel: return
        try:
            if sys.platform == "win32": os.startfile(self.sel)
            elif sys.platform == "darwin": subprocess.call(["open", self.sel])
            else: subprocess.call(["xdg-open", self.sel])
        except Exception as e: self._msg("error", "Error", str(e))

    def _transh(self):
        if not self.sel: return
        self.last_path = self.sel
        self._starttrans(False)

    def _delh(self):
        if not self.sel: return
        if not self._ask("Eliminar", "Borrar permanentemente?"): return
        try:
            base = self.sel.replace("_mejorado.wav", "")
            for s in ["_mejorado.wav", "_raw.wav", "_transcripcion.txt", "_con_timestamps.txt", "_adaptacion.txt"]:
                try: os.remove(base + s)
                except: pass
            self.history = [h for h in self.history if h["path"] != self.sel]
            for c in list(self.hist_frame.winfo_children()):
                if hasattr(c, '_path') and c._path == self.sel: c.destroy()
            self.sel = None
            self.bplay.configure(state="disabled")
            self.btransh.configure(state="disabled")
            self.bdel.configure(state="disabled")
        except Exception as e: self._msg("error", "Error", str(e))

    def _compile(self):
        if not self.compile_buffer:
            self._msg("info", "Compilacion", "Aun no hay transcripciones. Transcribe primero algunas clases.")
            return
        if self.config.get("colab_url"):
            self._apptxt(f"\nCompilando {len(self.compile_buffer)} clases en Colab...\n")
            threading.Thread(target=self._compile_worker, daemon=True).start()
        else:
            compiled = []
            for i, item in enumerate(self.compile_buffer, 1):
                compiled.append(f"\n{'='*60}\nCLASE {i}\n{'='*60}\n{item['text']}\n")
            text = "\n".join(compiled)
            self._set_adapt_text(text, "Compilacion Local", "")
            self._msg("info", "Compilado", f"Se han unido {len(self.compile_buffer)} transcripciones.")

    def _compile_worker(self):
        try:
            import requests
            url = self.config["colab_url"].rstrip("/")
            key = self.config.get("colab_key", "audioclass")
            r = requests.post(f"{url}/compile", data={"key": key, "title": "Compilacion AudioClass", "mode": "full"}, timeout=60)
            if r.status_code == 200:
                data = r.json()
                self.q.put(("log", f"\nCompilacion lista\n{data.get('preview', '')[:500]}...\n"))
            else:
                self.q.put(("log", f"\nError: {r.status_code}\n"))
        except Exception as e:
            self.q.put(("log", f"\nError: {e}\n"))

    def _togglerec(self):
        if not self.recording: self._startrec()

    def _disk_ok(self, mb_needed):
        """Comprueba que haya al menos mb_needed MB libres en el disco
        donde se guardan las grabaciones. Si no se puede comprobar
        (otro SO, permisos), asume que hay espacio."""
        try:
            free = shutil.disk_usage(OUTPUT_DIR).free
            return free >= mb_needed * 1024 * 1024
        except Exception:
            return True

    def _startrec(self):
        # Idempotencia: ya grabando (doble clic) o un procesamiento anterior
        # sigue en curso -> no arrancar otra vez. _proc_active (no _stop_done)
        # es la senal correcta: _stop_done se reinicia en _procsave, y guardar
        # con el bloquearia el ciclo grabar->parar->grabar para siempre.
        # _mic_probe_pending cubre el doble clic mientras dura el pre-check.
        if (getattr(self, "recording", False) or getattr(self, "_proc_active", False)
                or getattr(self, "_mic_probe_pending", False)):
            return
        if not self._disk_ok(100):
            self._msg("warning", "Espacio", "Necesitas 100 MB libres.")
            return
        try:
            sd.check_input_settings(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
        except Exception as e:
            self._msg("error", "Microfono", str(e))
            return
        # Si la prueba de microfono esta corriendo, abortarla: dos InputStreams
        # simultaneos pueden fallar en algunos host APIs de PortAudio.
        if getattr(self, "_mic_busy", False):
            try:
                if hasattr(self, "mic_test_top") and self.mic_test_top.winfo_exists():
                    self.mic_test_top.destroy()
            except Exception:
                pass
            self._mic_busy = False

        # ── Pre-check de nivel de entrada ──────────────────────────────────
        # Mide ~1.5 s ANTES de grabar (hilo; la UI sigue respondiendo). Si el
        # microfono esta muy debil (p90 < umbral), _mic_probe_done muestra una
        # advertencia visible y pide confirmacion; solo entonces arranca la
        # grabacion real (_begin_recording).
        self._mic_probe_pending = True
        try:
            self.lstatus.configure(text="🔍 Comprobando micrófono...", text_color=C["warn"])
        except Exception:
            pass
        threading.Thread(target=self._mic_probe_worker, daemon=True).start()

    def _mic_probe_worker(self):
        """Hilo del pre-check: captura ~1.5 s y calcula el p90 del RMS de
        tramos de 100 ms (misma metrica que optimizar_mic.py). Envia el nivel
        por la cola; None si el microfono no se puede abrir (entonces NO se
        bloquea la grabacion: el flujo real ya reporta el error si existe)."""
        try:
            win = int(0.1 * SAMPLE_RATE)
            buf = []

            def cb(indata, frames, ti, status):
                buf.append(indata.copy().flatten())

            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
                                blocksize=win, callback=cb):
                time.sleep(MIC_PROBE_SECONDS)
            if not buf:
                self.q.put(("mic_probe", None))
                return
            raw = np.concatenate(buf).flatten()
            fr = self.pipeline._frame_rms(raw.astype(np.float64), win, win // 2)
            p90 = float(np.percentile(fr, 90)) if len(fr) else 0.0
            self.q.put(("mic_probe", p90))
        except Exception as e:
            log_exc("mic probe")
            self.q.put(("mic_probe", None))

    def _mic_probe_done(self, level):
        """Resultado del pre-check (desde _poll): si el nivel de entrada es
        muy debil abre el dialogo de advertencia con p90 + medidor EN VIVO;
        si no, arranca la grabacion directo. Nunca bloquea la grabacion salvo
        que el usuario cancele explicitamente."""
        self._mic_probe_pending = False
        try:
            if level is not None and level < MIC_PROBE_P90_MIN:
                self._open_mic_warn_dialog(level)
                return
        except Exception:
            # Si abrir el dialogo falla (p.ej. la ventana se cerro), no
            # bloquear nunca la grabacion: se continua con el flujo normal.
            log_exc("mic probe done")
        try:
            self._begin_recording()
        except Exception:
            log_exc("begin recording")
            self.recording = False

    def _open_mic_warn_dialog(self, level):
        """Dialogo de advertencia de microfono debil ANTES de grabar: muestra
        el p90 medido y un medidor EN VIVO para que el usuario vea cuanto
        mejora al acercarse al microfono antes de decidir Continuar/Cancelar."""
        if getattr(self, "mic_warn_top", None) is not None:
            try:
                if self.mic_warn_top.winfo_exists():
                    self.mic_warn_top.lift()
                    self.mic_warn_top.focus_force()
                    return
            except Exception:
                pass

        self._mic_warn_decided = False
        # Running max del p90 de la sesion en vivo: arranca en el p90 medido
        # por el pre-check y solo sube si el usuario alcanza mejor senal.
        self.mic_warn_frames = []
        self.mic_warn_best_p90 = level
        # Tendencia del p90 para el mini-grafico: ventanas de 0.5 s (5
        # lecturas), max 20 barras = ultimos ~10 s. Arranca con el p90
        # medido por el pre-check para ver el punto de partida.
        self.mic_warn_bucket = []
        self.mic_warn_p90_hist = [level]
        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("🎤 Micrófono muy bajo")
        top.geometry("620x490")
        top.transient(self)
        top.grab_set()
        self.mic_warn_top = top

        self._lbl(top, "🎤 Micrófono muy bajo", font=("Segoe UI", 17, "bold"),
                  text_color=C["err"]).pack(pady=(16, 4))
        db = 20 * np.log10(max(level, 1e-6))
        self._lbl(top, f"Nivel medido: p90 = {level:.4f}  ({db:+.0f} dB) — por debajo del umbral de voz.",
                  font=("Segoe UI", 11), text_color=C["text"]).pack(pady=(0, 4))
        self._lbl(top, "Acércate al micrófono y habla: el medidor se actualiza en vivo.\n"
                       "La grabación puede salir casi en silencio si el nivel no sube.",
                  font=("Segoe UI", 11), text_color=C["muted"], wraplength=520).pack(pady=(0, 10))

        lvl_row = self._frame(top, fg_color="transparent")
        lvl_row.pack(fill="x", padx=36, pady=(0, 6))
        self._lbl(lvl_row, "Ahora:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        if CTK:
            self.mic_warn_bar = ctk.CTkProgressBar(lvl_row, width=300, height=16, corner_radius=8,
                                                   fg_color=C["button"], progress_color=C["muted"])
            self.mic_warn_bar.set(min(1.0, level * 10))
        else:
            self.mic_warn_bar = ttk.Progressbar(lvl_row, mode="determinate", maximum=100)
            self.mic_warn_bar['value'] = min(100, level * 1000)
        self.mic_warn_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.mic_warn_lbl = self._lbl(lvl_row, f"{db:+.0f} dB", font=("Segoe UI", 11), text_color=C["warn"])
        self.mic_warn_lbl.pack(side="left")

        best_row = self._frame(top, fg_color="transparent")
        best_row.pack(fill="x", padx=36, pady=(0, 4))
        self._lbl(best_row, "Mejor p90:", font=("Segoe UI", 11)).pack(side="left", padx=(0, 8))
        self.mic_warn_best_lbl = self._lbl(best_row, f"{level:.4f} ({db:+.0f} dB)  meta 0.03 (-30 dB)",
                                           font=("Segoe UI", 11, "bold"), text_color=C["warn"])
        self.mic_warn_best_lbl.pack(side="left")

        # Mini-grafico de tendencia: la evolucion del p90 al acercarse al
        # microfono, con la linea punteada de la meta (0.03 / -30 dB).
        trend_row = self._frame(top, fg_color="transparent")
        trend_row.pack(fill="x", padx=36, pady=(2, 2))
        self._lbl(trend_row, "Tendencia p90 (10 s):", font=("Segoe UI", 9),
                  text_color=C["muted"]).pack(side="left", padx=(0, 8))
        self.mic_warn_trend = tk.Canvas(trend_row, width=380, height=40, bg=C["card"],
                                        highlightthickness=1, highlightbackground=C["border"])
        self.mic_warn_trend.pack(side="left", fill="x", expand=True)

        self._lbl(top, "Meta: que la barra suba a verde (voz ≥ -30 dB / p90 ≥ 0.03).",
                  font=("Segoe UI", 10), text_color=C["muted"]).pack(pady=(0, 10))

        btns = self._frame(top, fg_color="transparent")
        btns.pack(pady=(0, 6))
        self._btn(btns, "🎙️ Continuar grabando", lambda: self._mic_warn_decide(True),
                  width=230, height=42, font=("Segoe UI", 12, "bold"),
                  fg_color=C["err"], hover_color=C["err"]).pack(side="left", padx=(0, 10))
        self._btn(btns, "Cancelar", lambda: self._mic_warn_decide(False),
                  width=120, height=42, font=("Segoe UI", 12, "bold")).pack(side="left")
        # Ruta de correccion sin cancelar: abre el optimizador y aplica la
        # optimizacion (nivel 100% + desmute + boost) directamente.
        opt_row = self._frame(top, fg_color="transparent")
        opt_row.pack(pady=(0, 14))
        self._btn(opt_row, "⚡ Abrir optimizador (corregir nivel ahora)",
                  lambda: self._mic_warn_open_opt(),
                  width=340, height=40, font=("Segoe UI", 12, "bold"),
                  fg_color=C["ok"], hover_color=C["ok"]).pack()
        top.protocol("WM_DELETE_WINDOW", lambda: self._mic_warn_decide(False))

        # Medidor en vivo mientras el dialogo esta abierto: el hilo mide el
        # nivel y envia el RMS de cada bloque (~100 ms) por la cola (_poll
        # actualiza la barra). Se detiene al decidir o a los 60 s.
        threading.Thread(target=self._mic_live_probe_worker, daemon=True).start()

    def _update_mic_warn_best(self, r):
        """Actualiza el 'Mejor p90' en vivo del dialogo de advertencia: ventana
        de ~3 s (30 lecturas) y running max del p90, para que el usuario sepa
        si YA alcanzo la meta (>= 0.03) aunque luego baje la voz."""
        frames = getattr(self, "mic_warn_frames", None)
        if frames is None:
            frames = []
            self.mic_warn_frames = frames
        frames.append(r)
        if len(frames) > 30:
            del frames[:-30]
        p90_now = float(np.percentile(frames, 90)) if frames else r
        best = max(getattr(self, "mic_warn_best_p90", 0.0), p90_now)
        self.mic_warn_best_p90 = best
        # Tendencia del p90: agrupa lecturas en ventanas de 0.5 s (5 lecturas)
        # y guarda su p90 (max 20 barras = ~10 s) para el mini-grafico.
        bucket = getattr(self, "mic_warn_bucket", None)
        if bucket is None:
            bucket = []
            self.mic_warn_bucket = bucket
        bucket.append(r)
        if len(bucket) >= 5:
            p90b = float(np.percentile(bucket, 90)) if bucket else r
            hist = getattr(self, "mic_warn_p90_hist", None)
            if hist is None:
                hist = []
                self.mic_warn_p90_hist = hist
            hist.append(p90b)
            if len(hist) > 20:
                del hist[:-20]
            del bucket[:]
            self._draw_mic_warn_trend()
        try:
            if getattr(self, "mic_warn_best_lbl", None) is not None and self.mic_warn_best_lbl.winfo_exists():
                bdb = 20 * np.log10(max(best, 1e-6))
                meta = "✓ ¡Meta alcanzada!" if best >= 0.03 else "meta 0.03 (-30 dB)"
                self.mic_warn_best_lbl.configure(text=f"{best:.4f} ({bdb:+.0f} dB)  {meta}",
                                                 text_color=C["ok"] if best >= 0.03 else C["warn"])
        except Exception:
            pass
        return best

    def _draw_mic_warn_trend(self):
        """Mini-grafico de la tendencia del p90 en el dialogo de advertencia:
        una barra por ventana de 0.5 s (ultimos ~10 s) y linea punteada de la
        meta (0.03 / -30 dB). Verde = meta alcanzada en esa ventana."""
        cv = getattr(self, "mic_warn_trend", None)
        if cv is None:
            return
        try:
            if not cv.winfo_exists():
                return
            cv.delete("all")
            w = int(cv.winfo_width())
            h = int(cv.winfo_height())
            if w < 20 or h < 10:
                return
            hist = getattr(self, "mic_warn_p90_hist", []) or []
            MAXB = 20
            bw = w / MAXB
            base = h - 2
            for i, v in enumerate(hist):
                db = 20 * np.log10(max(v, 1e-6))
                frac = min(1.0, max(0.0, (db + 60) / 60))
                bh = max(1.0, frac * (h - 6))
                x0 = i * bw
                col = C["ok"] if v >= 0.03 else (C["warn"] if v >= 0.01 else C["accent"])
                cv.create_rectangle(x0, base - bh, x0 + bw - 2, base, fill=col, outline="")
            # Linea de la meta: 0.03 ≈ -30.5 dB ≈ 49% de la escala
            fg = max(0.0, min(1.0, (20 * np.log10(0.03) + 60) / 60))
            yg = base - fg * (h - 6)
            cv.create_line(0, yg, w, yg, fill=C["ok"], dash=(2, 2))
        except Exception:
            pass

    def _mic_live_probe_worker(self):
        """Mide el nivel en vivo mientras el dialogo de advertencia esta
        abierto. Envia ("mic_live", rms) por la cola; nunca toca widgets."""
        try:
            win = int(0.1 * SAMPLE_RATE)
            t0 = time.time()

            def cb(indata, frames, ti, status):
                r = float(np.sqrt(np.mean(indata.astype(np.float64) ** 2))) if len(indata) else 0.0
                self.q.put(("mic_live", r))

            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
                                blocksize=win, callback=cb):
                while not getattr(self, "_mic_warn_decided", False) and time.time() - t0 < 60:
                    time.sleep(0.1)
        except Exception:
            log_exc("mic live probe")

    def _mic_warn_open_opt(self):
        """Boton 'Abrir optimizador' del dialogo de advertencia: cierra la
        advertencia (detiene el medidor en vivo), abre el optimizador y lanza
        la optimizacion directamente — corrige el nivel sin cancelar. La
        grabacion no arranca aqui: al terminar, el usuario pulsa Grabar y el
        pre-check ya pasa."""
        self._mic_warn_decided = True
        try:
            if getattr(self, "mic_warn_top", None) is not None:
                try:
                    if self.mic_warn_top.winfo_exists():
                        self.mic_warn_top.destroy()
                except Exception:
                    pass
                self.mic_warn_top = None
        except Exception:
            pass
        try:
            self.lstatus.configure(text="Listo", text_color=C["ok"])
        except Exception:
            pass
        try:
            self._open_mic_opt()
            self._mic_opt_start(True)
        except Exception:
            log_exc("mic warn open opt")

    def _mic_warn_decide(self, continuar):
        """Boton del dialogo de advertencia: cierra, detiene el medidor en
        vivo y arranca la grabacion (True) o cancela restaurando la UI (False)."""
        self._mic_warn_decided = True
        try:
            if getattr(self, "mic_warn_top", None) is not None:
                try:
                    if self.mic_warn_top.winfo_exists():
                        self.mic_warn_top.destroy()
                except Exception:
                    pass
                self.mic_warn_top = None
        except Exception:
            pass
        if continuar:
            try:
                self._begin_recording()
            except Exception:
                log_exc("begin recording")
                self.recording = False
        else:
            try:
                self.lstatus.configure(text="Listo", text_color=C["ok"])
            except Exception:
                pass

    def _prompt_rec_consent(self):
        """Aviso de grabacion (una vez): el usuario debe informar a los demas
        participantes de que se esta grabando (requisito en estados all-party
        y en el ambito laboral). Devuelve True si se acepta grabar."""
        return self._ask(
            "🔴 Aviso de grabación",
            "AudioClass grabará el audio de esta sesión.\n\n"
            "Si hay otras personas, debes informarles de que la sesión se está grabando "
            "y obtener su consentimiento cuando la ley lo exija (en particular en estados "
            "de consentimiento de todos los participantes y en entornos laborales).\n\n"
            "¿Quieres comenzar la grabación?")

    def _begin_recording(self):
        """Arranca la grabacion real (invocada por _mic_probe_done tras el
        pre-check de nivel de entrada). Contiene el cuerpo original de
        _startrec a partir de self.recording = True."""
        # V1 Grabar sin consentimiento: aviso obligatorio la primera vez.
        if not self.config.get("rec_consent_ack", False):
            if not self._prompt_rec_consent():
                try:
                    self.lstatus.configure(text="Listo", text_color=C["ok"])
                except Exception:
                    pass
                return
            self.config["rec_consent_ack"] = True
            save_config(self.config)
        self.recording = True
        self.stop_ev.clear()
        self._stop_done = False
        self.buffer = []
        self._audio_overflows = 0
        self.vu_clips = 0
        self.vu_low = 0
        self.vu_rms_hist = []
        self.vu_static = False
        self.vu_rms_hist_full = []
        # ── Streaming a disco (#4): clases largas no acumulan cientos de MB en
        # RAM. El audio se vuelca a un archivo temporal .raw (float32) mientras
        # se graba y en memoria solo quedan las ultimas ~2s para el waveform.
        # _procsave lee el archivo completo al detener.
        # Streaming: abrir el temporal. Si falla, revertir el estado para que
        # la UI no quede colgada en "GRABANDO".
        try:
            self._rec_raw_path = os.path.join(tempfile.gettempdir(), f"ac_rec_{int(time.time() * 1000)}.raw")
            self._rec_fp = open(self._rec_raw_path, "wb")
        except Exception as e:
            log_exc("startrec open raw")
            self.recording = False
            self._msg("error", "Grabacion", f"No se pudo iniciar: {str(e)[:60]}")
            return
        self._rec_bytes = 0
        self._flusher_thread = None
        if CTK:
            self.vu_bar.set(0)
            self.vu_lbl.configure(text="-∞ dB", text_color=C["muted"])
        else:
            self.vu_bar['value'] = 0
            self.vu_lbl.configure(text="-∞ dB", fg=C["muted"])
        try:
            self.vu_warn.configure(text="")
            if hasattr(self, "vu_hist"):
                self.vu_hist.delete("all")
        except Exception:
            pass
        self.vizbuf = np.zeros(VISUAL_SAMPLES, dtype=np.float32)
        self.cancel = False
        self._set_step(1)

        self.brec.pack_forget()
        # before=self.btr: Tk re-inserta el widget al FINAL del orden de pack
        # por defecto (despues del VU meter, que ahora es ancho) y el boton
        # 'Detener' quedaba lejos o fuera de la ventana. Empaquetarlo antes de
        # 'Transcribir' lo coloca exactamente donde estaba el boton rojo.
        self.bstop.pack(side="left", padx=(18, 12), pady=16, before=self.btr)
        self.lstatus.configure(text="● GRABANDO", text_color=C["err"])
        self.btr.configure(state="disabled")
        self.bts.configure(state="disabled")
        self.bpdf.configure(state="disabled")
        self.bdocx.configure(state="disabled")
        self.bdocs.configure(state="disabled")
        self._disable_adapt_buttons()
        self._cleartxt()
        self._clear_adapt()
        self._apptxt(f"Grabacion iniciada...\nPerfil: {self.pipeline.profile}\nManten silencio los primeros segundos para perfil de ruido.\n\n")

        self.t0rec = time.time()
        self._updtimer()
        try:
            threading.Thread(target=self._recloop, daemon=True).start()
            self._flusher_thread = threading.Thread(target=self._rec_flusher, daemon=True)
            self._flusher_thread.start()
        except Exception as e:
            log_exc("startrec threads")
            self.recording = False
            try:
                self._rec_fp.close()
            except Exception:
                pass
            self._msg("error", "Grabacion", f"No se pudo iniciar: {str(e)[:60]}")
            return
        if MPL: self._updviz()
        self._updvu()

    def _stoprec(self):
        # Idempotente: un doble clic en "Detener" no debe lanzar dos _procsave
        # en paralelo sobre el mismo archivo temporal.
        if getattr(self, "_stop_done", False):
            return
        self._stop_done = True
        self.recording = False
        self.stop_ev.set()
        # Proteger la UI: si una operacion Tk lanza (p.ej. TclError al cerrar
        # la ventana en pleno clic), _stop_done no debe quedar en True o la app
        # quedaria sin poder volver a grabar. Con esto el flujo siempre llega a
        # un punto de reinicio (camino sin audio o el finally de _procsave).
        try:
            self.bstop.pack_forget()
            self.brec.pack(side="left", padx=(18, 12), pady=16, before=self.btr)
            self.lstatus.configure(text="Procesando audio profesional...", text_color=C["warn"])
            self.ltime.configure(text="")
        except Exception:
            pass
        # El medidor se apaga (el ticker _updvu deja de re-programarse solo)
        try:
            if CTK:
                self.vu_bar.set(0)
                self.vu_lbl.configure(text="-∞ dB", text_color=C["muted"])
            else:
                self.vu_bar['value'] = 0
                self.vu_lbl.configure(text="-∞ dB", fg=C["muted"])
            self.vu_warn.configure(text="")
            if hasattr(self, "vu_hist"):
                self.vu_hist.delete("all")
        except Exception:
            pass

        # Esperar a que el flusher termine de volcar el resto ANTES de decidir
        # si hubo audio: el flusher escribe al archivo y luego incrementa
        # _rec_bytes, asi que leerlo sin join podia dar un falso "sin audio".
        if getattr(self, "_flusher_thread", None):
            try:
                self._flusher_thread.join(timeout=10)
            except Exception:
                pass
            self._flusher_thread = None
        # Con streaming, el buffer en memoria puede estar vacio aunque haya
        # audio (ya volcado a disco): la senal de captura es el archivo .raw.
        if self._rec_bytes == 0 and not self.buffer:
            self.lstatus.configure(text="No se capturo audio", text_color=C["warn"])
            try:
                self._rec_fp.close()
            except Exception:
                pass
            try:
                if os.path.exists(getattr(self, "_rec_raw_path", "")):
                    os.remove(self._rec_raw_path)
                    self._rec_raw_path = ""
            except Exception:
                pass
            # Reabrir el ciclo: sin audio no hay procsave que reinicie el flag.
            self._stop_done = False
            return
        threading.Thread(target=self._procsave, daemon=True).start()

    def _recloop(self):
        # El callback de audio debe ser lo mas ligero posible: si tarda mas que
        # la duracion de un bloque, PortAudio pierde muestras y la grabacion
        # sale con estatica y cortes. Solo se copia el bloque a la lista; el
        # buffer visual se reconstruye en el hilo principal (_updviz) y un
        # flusher (daemon) lo va volcando a disco en paralelo.
        def cb(indata, frames, ti, status):
            if status and status.input_overflow:
                self._audio_overflows += 1
            if self.recording:
                # flatten() devuelve SIEMPRE una copia 1-D (CHUNK_SIZE,).
                # No usar .ravel() aqui: seria una vista del buffer interno de
                # PortAudio que se reutiliza en el siguiente bloque y corrompe
                # el audio; los bloques 2-D (CHUNK_SIZE,1) rompian v[-n:]=recent
                # en _updviz (broadcast error).
                self.buffer.append(indata.flatten())
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
                                blocksize=CHUNK_SIZE, callback=cb):
                self.stop_ev.wait()
        except Exception as e:
            log_exc("recloop")
            self.q.put(("status", f"Error: {str(e)[:40]}"))
            self.recording = False

    def _rec_flusher(self):
        """Vuelca el audio grabado a disco por tramos. En RAM solo se conservan
        las ultimas ~2s (para el waveform); el resto se escribe como float32
        crudo al archivo temporal. Al detener, vuelca el resto y cierra."""
        KEEP = int(np.ceil(VISUAL_SAMPLES / CHUNK_SIZE)) + 4   # ~2s + margen
        try:
            while self.recording:
                time.sleep(1.0)
                n = len(self.buffer)
                if n > KEEP:
                    cut = n - KEEP
                    arr = np.concatenate(self.buffer[:cut]).flatten()
                    self._rec_fp.write(np.ascontiguousarray(arr, dtype=np.float32).tobytes())
                    self._rec_bytes += len(arr) * 4
                    del self.buffer[:cut]
            # Vaciado final al detener
            if self.buffer:
                arr = np.concatenate(self.buffer).flatten()
                self._rec_fp.write(np.ascontiguousarray(arr, dtype=np.float32).tobytes())
                self._rec_bytes += len(arr) * 4
                self.buffer = []
        except Exception as e:
            log_exc("rec_flusher")
        finally:
            try:
                self._rec_fp.close()
            except Exception:
                pass

    def _updtimer(self):
        if self.recording:
            m, s = divmod(int(time.time() - self.t0rec), 60)
            tstr = f"{m:02d}:{s:02d}"
            # El cronometro se muestra junto a GRABANDO (area de controles,
            # siempre visible) y tambien en el pie si este cabe en pantalla.
            try:
                self.ltime.configure(text=tstr)
            except Exception:
                pass
            # Indicador REC parpadeante mientras se graba
            dot = "●" if int(time.time() * 2) % 2 == 0 else "○"
            self.lstatus.configure(text=f"{dot} GRABANDO · {tstr}", text_color=C["err"])
            self.after(500, self._updtimer)

    def _updviz(self):
        if self.recording and MPL:
            if self.buffer:
                # Solo se usan las ultimas muestras; concatenar todo el buffer
                # cada fotograma seria O(n) en clases largas.
                need = int(np.ceil(VISUAL_SAMPLES / CHUNK_SIZE)) + 2
                # Los bloques del callback son 2-D (CHUNK_SIZE, 1): aplanar a 1-D
                # o v[-n:] = recent lanza broadcast error en los primeros frames.
                recent = np.concatenate(self.buffer[-need:]).ravel()
                n = len(recent)
                if n >= VISUAL_SAMPLES:
                    self.vizbuf = recent[-VISUAL_SAMPLES:]
                else:
                    v = np.zeros(VISUAL_SAMPLES, dtype=np.float32)
                    v[-n:] = recent
                    self.vizbuf = v
            self.line.set_data(np.arange(VISUAL_SAMPLES), self.vizbuf)
            mx = max(0.1, np.max(np.abs(self.vizbuf)) * 1.2)
            self.ax.set_ylim(-mx, mx)
            self.canvas.draw_idle()
            self.after(50, self._updviz)

    def _updvu(self):
        """Medidor de nivel en vivo mientras se graba: RMS de las ultimas
        muestras, dB y deteccion de recorte (picos cerca de 0 dBFS). Corre en
        el hilo principal (after), asi funciona aunque no haya matplotlib."""
        if not getattr(self, "recording", False):
            return
        try:
            rms, peak = 0.0, 0.0
            if self.buffer:
                need = 6  # ultimas ~0.6 s
                recent = np.concatenate(self.buffer[-need:])
                x = recent.astype(np.float64)
                rms = float(np.sqrt(np.mean(x * x))) if len(x) else 0.0
                peak = float(np.max(np.abs(x))) if len(x) else 0.0
            db = 20 * np.log10(max(rms, 1e-6))

            # Deteccion de "audio sin voz" (estatica): la voz real oscila entre
            # palabras y pausas (el RMS varia mucho), mientras que la estatica o
            # el ruido de fondo tiene un RMS CASI constante. Con una ventana de
            # ~3.2s (40 lecturas de 80ms), si el coeficiente de variacion
            # (std/mean) es muy bajo y el nivel no es silencio, es estatica.
            self.vu_rms_hist.append(rms)
            if len(self.vu_rms_hist) > 40:
                self.vu_rms_hist.pop(0)
            # Historico de los ultimos 10 s (125 lecturas de 80 ms) para el
            # mini-grafico debajo del medidor.
            self.vu_rms_hist_full.append(rms)
            if len(self.vu_rms_hist_full) > 125:
                self.vu_rms_hist_full.pop(0)
            if len(self.vu_rms_hist) >= 25 and time.time() - self.t0rec > 3.0:
                h = np.array(self.vu_rms_hist)
                hm = float(np.mean(h))
                hs = float(np.std(h))
                # Umbral de sensibilidad configurable (deslizador): mas alto =
                # detecta estatica mas facil (senal mas constante -> menor CV).
                sens = max(0.05, min(0.60, getattr(self, "vu_sens", 0.25)))
                # Des-latch: refleja la ventana ACTUAL (si luego hablas, el
                # aviso desaparece y el log final no es engañoso)
                self.vu_static = (hm > 0.02 and hs / hm < sens)
            self._draw_vu_hist()

            # Escala: -60 dB = 0% ... 0 dBFS = 100%
            frac = min(1.0, max(0.0, (db + 60) / 60))
            if CTK:
                self.vu_bar.set(frac)
                col = C["err"] if peak > 0.95 else (C["warn"] if db > -12 else C["accent"])
                self.vu_bar.configure(progress_color=col)
            else:
                self.vu_bar['value'] = min(100, frac * 100)
            if peak > 0.95:
                self.vu_clips += 1
                txt = f"{db:+.0f} dB ⚠ RECORTE"
                col = C["err"]
            elif db < -45:
                # Micro muy bajo: se ignora durante los primeros segundos porque
                # la app pide silencio para el perfil de ruido (falso positivo).
                if time.time() - self.t0rec > 2.0:
                    self.vu_low += 1
                    txt = f"{db:+.0f} dB ⚡ Bajo"
                    col = C["warn"]
                else:
                    txt = f"{db:+.0f} dB"
                    col = C["muted"]
            else:
                txt = f"{db:+.0f} dB"
                col = C["muted"]
            if CTK:
                self.vu_lbl.configure(text=txt, text_color=col)
            else:
                self.vu_lbl.configure(text=txt, fg=col)
            # Aviso en vivo de audio sin voz (estatica) mientras se graba
            if self.vu_static:
                wl = "⚠ Audio sin voz detectada"
                if CTK:
                    self.vu_warn.configure(text=wl, text_color=C["warn"])
                else:
                    self.vu_warn.configure(text=wl, fg=C["warn"])
        except Exception:
            pass
        self.after(80, self._updvu)

    def _draw_vu_hist(self):
        """Mini-grafico de los ultimos 10 s de nivel: barras proporcionales al
        RMS (escala -60..0 dBFS), doradas con la paleta activa y con franja
        ambar inferior mientras se detecte estatica (audio sin voz)."""
        cv = getattr(self, "vu_hist", None)
        if cv is None:
            return
        try:
            cv.delete("all")
            w = int(cv.winfo_width())
            h = int(cv.winfo_height())
            if w < 10 or h < 10:
                return
            hist = getattr(self, "vu_rms_hist_full", [])
            n = len(hist)
            if not n:
                return
            bw = w / 125.0
            base = h - 2
            for i, r in enumerate(hist):
                db = 20 * np.log10(max(r, 1e-6))
                frac = min(1.0, max(0.0, (db + 60) / 60))
                bh = max(1.0, frac * (h - 5))
                x0 = i * bw
                col = C["accent"]
                if db > -12:
                    col = C["warn"]
                if db > -3:
                    col = C["err"]
                cv.create_rectangle(x0, base - bh, x0 + max(bw - 0.4, 0.6), base,
                                    fill=col, outline="")
            if getattr(self, "vu_static", False):
                cv.create_rectangle(0, h - 3, w, h, fill=C["warn"], outline="")
        except Exception:
            pass

    def _vu_sens_changed(self, val):
        """Callback del deslizador de sensibilidad: guarda el umbral en config
        (persistente) y actualiza la etiqueta de valor. El guard de comparacion
        evita escribir config a cada tick del arrastre (ttk.Scale dispara el
        comando continuamente en modo fallback)."""
        try:
            v = max(0.05, min(0.60, round(float(val), 2)))
        except Exception:
            return
        self.vu_sens = v
        lbl = getattr(self, "vu_sens_val", None)
        if lbl is not None:
            try:
                if CTK:
                    lbl.configure(text=f"{v:.2f}", text_color=C["muted"])
                else:
                    lbl.configure(text=f"{v:.2f}", fg=C["muted"])
            except Exception:
                pass
        if abs(self.config.get("vu_sensitivity", 0.25) - v) > 1e-6:
            self.config["vu_sensitivity"] = v
            save_config(self.config)

    def _procsave(self):
        # Flag activo: _close no debe borrar el temporal mientras este hilo lo
        # esta leyendo (el finally de aqui lo limpia al terminar, tambien en
        # error). Sin esto, cerrar justo tras detener daba un audio vacio.
        # my_raw se captura al INICIO: si el usuario vuelve a grabar antes de
        # que este finally corra, _rec_raw_path ya apunta a la grabacion nueva
        # y no debe borrarse (solo se limpia si sigue siendo el nuestro).
        my_raw = getattr(self, "_rec_raw_path", "")
        self._proc_active = True
        try:
            # #4 Streaming: el audio completo vive en el archivo temporal
            # (float32 crudo) que fue volcando el flusher durante la grabacion.
            raw = np.zeros(0, dtype=np.float32)
            if my_raw and os.path.exists(my_raw):
                with open(my_raw, "rb") as f:
                    raw = np.frombuffer(f.read(), dtype=np.float32).astype(np.float32).flatten()
            if len(raw) == 0 and self.buffer:
                raw = np.concatenate(self.buffer).flatten()

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dur = len(raw) / SAMPLE_RATE

            rp = os.path.join(OUTPUT_DIR, f"clase_{ts}_raw.wav")
            self._savewav(rp, raw)
            log_info(f"Audio crudo guardado: {rp} ({dur:.1f}s)")
            self.q.put(("log", "Audio original guardado\n"))

            self.q.put(("status", "Aplicando pipeline profesional..."))

            def progress(step, total, name):
                self.q.put(("log", f"{step}/{total}: {name}\n"))
                self.q.put(("progress", (step / total, name)))

            proc = self.pipeline.process(raw, progress_callback=progress)

            pp = os.path.join(OUTPUT_DIR, f"clase_{ts}_mejorado.wav")
            self._savewav(pp, proc)

            self.last_path = pp
            self.q.put(("log", "Audio mejorado guardado\n\n"))

            # #8 Metadata por grabacion: JSON junto a los WAV con duracion,
            # perfil, modelo y metricas de calidad (para el historial e informes).
            try:
                meta = {
                    "fecha": ts,
                    "duracion_s": round(dur, 2),
                    "perfil": self.config.get("audio_profile", ""),
                    "modelo": getattr(self, "last_model", "Whisper"),
                    "overflows": getattr(self, "_audio_overflows", 0),
                    "vu_clips": getattr(self, "vu_clips", 0),
                    "vu_low": getattr(self, "vu_low", 0),
                    "vu_static": bool(getattr(self, "vu_static", False)),
                }
                with open(os.path.join(OUTPUT_DIR, f"clase_{ts}.json"), "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=2, ensure_ascii=False)
            except Exception:
                log_exc("metadata")

            if getattr(self, "_audio_overflows", 0) > 0:
                self.q.put(("log", f"⚠ Se detectaron {self._audio_overflows} desbordamientos de audio.\n"
                                   "Puede haber cortes o estática. Cierra programas pesados y vuelve a grabar si es necesario.\n"))
            if getattr(self, "vu_clips", 0) > 0:
                self.q.put(("log", f"⚠ Se detectaron {self.vu_clips} momentos de recorte (volumen al límite).\n"
                                   "Baja el volumen del micrófono o aléjate un poco para mejor calidad.\n"))
            # Umbral minimo (5 lecturas ≈ 0.4s) para evitar falsos positivos
            if getattr(self, "vu_low", 0) > 5:
                self.q.put(("log", f"⚠ Nivel de micro muy bajo detectado ({self.vu_low} lecturas).\n"
                                   "Acerca el micrófono o sube el volumen de entrada para mejor transcripción.\n"))
            # Audio sin voz (estatica): nivel casi constante -> no hay voz real
            if getattr(self, "vu_static", False):
                self.q.put(("log", "⚠ Audio sin voz detectada (nivel constante / estática).\n"
                                   "La transcripción saldrá vacía. Revisa el micrófono, el cable o el nivel de entrada, y vuelve a grabar.\n"))
            self.q.put(("status", "Listo para transcribir"))
            self.q.put(("enable_rec", None))
            self.q.put(("addhist", pp))

            if self.easy_var.get() and self.config.get("gemini_api_key"):
                self.q.put(("log", "\nModo Facil: iniciando transcripcion automatica...\n"))
                self.after(500, lambda: self._starttrans(False, auto_adapt=True))

        except Exception as e:
            log_exc("procsave")
            self.q.put(("status", f"Error: {str(e)[:50]}"))
            self.q.put(("log", f"Error: {e}\n"))
        finally:
            # Limpiar el temporal SIEMPRE (exito o error): no dejar .raw en
            # %TEMP% que se acumulen en cierres anormales. Se hace ANTES de
            # liberar _proc_active: mientras el flag sigue en True, _startrec
            # no puede arrancar una grabacion nueva, asi que _rec_raw_path
            # todavia es my_raw y la comparacion siempre acierta (sin race).
            try:
                if my_raw and self._rec_raw_path == my_raw and os.path.exists(my_raw):
                    os.remove(my_raw)
                    self._rec_raw_path = ""
            except Exception:
                pass
            # Reabrir el ciclo grabar->parar->grabar (exito o error).
            self._proc_active = False
            self._stop_done = False

    def _savewav(self, path, arr):
        wavfile.write(path, SAMPLE_RATE, np.int16(np.clip(arr, -1.0, 1.0) * 32767))

    def _starttrans(self, timestamps, auto_adapt=False):
        if not self.last_path or not os.path.exists(self.last_path):
            self._msg("warning", "Sin audio", "Primero graba y deten una clase.")
            return

        # Guarda anti doble inicio (boton pulsado + auto-reanudacion pendiente)
        if self._transcribing:
            return

        mode = self.mode_var.get()

        if mode == "cloud" and not self.config.get("colab_url"):
            self._msg("warning", "Cloud", "Configura la URL de Colab en Configuracion.")
            return

        self.cancel = False
        self._last_trans_req = (timestamps, auto_adapt)
        # Oculta la insignia 'Revisado por IA' hasta que termine esta pasada
        if hasattr(self, "lbadge"):
            try:
                self.lbadge.pack_forget()
            except Exception:
                pass
        # Limpia una cancelacion previa: si el usuario cancelo la transcripcion
        # anterior, stop_ev queda seteado y mataria la nueva (cancelled inmediato).
        self.stop_ev.clear()
        self.btr.configure(state="disabled")
        self.bts.configure(state="disabled")
        self.bpdf.configure(state="disabled")
        self.bdocx.configure(state="disabled")
        self.bdocs.configure(state="disabled")
        self.bcancel.configure(state="normal")
        self._disable_adapt_buttons()

        if CTK: self.pbar.set(0)
        else: self.pbar['value'] = 0
        self.lprog.configure(text="Iniciando transcripcion...")
        self._apptxt("\nIniciando transcripcion...\n")

        self._transcribing = True
        self._trans_start = time.time()
        self._trans_msg = "Iniciando transcripción..."
        self._trans_frac = 0.0      # progreso actual (para ETA del ticker)
        self._last_partial_len = 0  # throttle del streaming en vivo
        self._trans_ticker()

        if mode == "local":
            if not self.local_engine.ready:
                if self.local_engine.loading:
                    # El modelo sigue cargandose: la transcripcion se iniciara
                    # sola en cuanto termine (model_ready). No bloquear la UI.
                    self._pending_trans = (timestamps, auto_adapt)
                    self.lprog.configure(text="⏳ Cargando modelo Whisper... se iniciará solo", text_color=C["warn"])
                    self._apptxt("\nCargando modelo Whisper (la primera vez puede tardar)...\n")
                    self.q.put(("enable", None))
                    return
                err = self.local_engine.error or "causa desconocida"
                self._msg("error", "Modelo local no disponible",
                          f"No se pudo cargar Whisper:\n{err}\n\nRevisa la instalación del modelo o "
                          "usa el modo Cloud (☁️) en Configuración.")
                self.lprog.configure(text="Modelo local no disponible", text_color=C["err"])
                self.q.put(("enable", None))
                return
            threading.Thread(target=self._trans_local_worker, args=(self.last_path, timestamps, auto_adapt), daemon=True).start()
        else:
            threading.Thread(target=self._trans_cloud_worker, args=(self.last_path, timestamps, auto_adapt), daemon=True).start()

    def _trans_local_worker(self, path, timestamps, auto_adapt):
        try:
            def progress(current, total, msg):
                self.q.put(("progress", (current / total, msg)))

            # Streaming (mejora #3): el motor emite el texto parcial acumulado
            # por chunk; la UI lo muestra en vivo mientras transcribe.
            def partial(txt):
                self.q.put(("partial", txt))

            result = self.local_engine.transcribe(path, True,
                                                   cancel_event=self.stop_ev,
                                                   progress_callback=progress,
                                                   partial_callback=partial)

            if result.get("cancelled"):
                self.q.put(("log", "\nCancelado.\n"))
                self.q.put(("status", "Cancelado"))
                self.q.put(("enable", None))
                return

            # Pre-validacion de silencio (mejora #2): el motor detecto que el
            # WAV es silencio digital y no gasto tiempo en transcribirlo.
            if result.get("silence"):
                self.q.put(("log", f"\n⚠ {result.get('silence_msg', 'Audio silencioso')}\n"))
                self.q.put(("status", "Audio silencioso"))
                self.q.put(("enable", None))
                return

            if "error" in result:
                raise Exception(result["error"])

            omit = result.get("chunks_omitidos", 0)
            if omit:
                self.q.put(("log", f"⚠ {omit} segmento(s) de audio no se pudieron "
                                   "transcribir (whisper falló o se quedó colgado en "
                                   "ellos); la transcripción es parcial.\n"))

            self._process_transcription_result(result, path, timestamps, auto_adapt)

        except Exception as e:
            log_exc("transcripcion local")
            self.q.put(("log", f"\nError: {e}\n"))
            self.q.put(("status", "Error de transcripcion"))
            self.q.put(("trans_err", str(e)))
            self.q.put(("enable", None))

    def _trans_cloud_worker(self, path, timestamps, auto_adapt):
        try:
            def progress(current, total, msg):
                self.q.put(("progress", (current / total, msg)))

            result = self.cloud_engine.transcribe(path, timestamps,
                                                   cancel_event=self.stop_ev,
                                                   progress_callback=progress)

            if result.get("cancelled"):
                self.q.put(("log", "\nCancelado.\n"))
                self.q.put(("status", "Cancelado"))
                self.q.put(("enable", None))
                return

            if "error" in result:
                raise Exception(result["error"])

            omit = result.get("chunks_omitidos", 0)
            if omit:
                self.q.put(("log", f"⚠ {omit} segmento(s) de audio no se pudieron "
                                   "transcribir (whisper falló o se quedó colgado en "
                                   "ellos); la transcripción es parcial.\n"))

            self._process_transcription_result(result, path, timestamps, auto_adapt)

        except Exception as e:
            self.q.put(("log", f"\nError Cloud: {e}\n"))
            self.q.put(("status", "Error de conexion"))
            self.q.put(("trans_err", str(e)))
            self.q.put(("enable", None))

    def _process_transcription_result(self, result, path, timestamps, auto_adapt):
        text = result.get("text", "")
        self.last_text = text
        self.last_segments = result.get("segments", [])
        self.last_model = result.get("model", "Whisper")

        base = os.path.splitext(os.path.basename(path))[0]
        if timestamps and self.last_segments:
            tp = os.path.join(OUTPUT_DIR, f"{base}_con_timestamps.txt")
            with open(tp, "w", encoding="utf-8") as f:
                f.write("Transcripcion con timestamps\n")
                f.write(f"Generada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Modelo: {result.get('model', '?')} | {result.get('device', '?')}\n\n")
                for s in self.last_segments:
                    ts = str(timedelta(seconds=int(s["start"])))[2:]
                    te = str(timedelta(seconds=int(s["end"])))[2:]
                    f.write(f"[{ts} - {te}] {s['text'].strip()}\n")
                f.write("\nTEXTO COMPLETO:\n" + text)
        else:
            tp = os.path.join(OUTPUT_DIR, f"{base}_transcripcion.txt")
            with open(tp, "w", encoding="utf-8") as f:
                f.write(f"Generada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Modelo: {result.get('model', '?')} | {result.get('device', '?')}\n\n" + text)

        # Garantiza que la barra muestre el 100% al terminar, aunque el ultimo
        # mensaje del motor fuese una estimacion intermedia (ej. 99%).
        self.q.put(("progress", (1.0, "✓ 100% · Transcripción completada")))
        self.q.put(("trans_done", text))
        _be = result.get("backend", "")
        _be_str = f" | {_be}" if _be else ""
        self.q.put(("log", f"\nTranscripcion completada\n{result.get('model','?')} | "
                            f"{result.get('device','?')}{_be_str}\nGuardado\n"))
        self.q.put(("status", "Transcripcion lista"))
        self.q.put(("enable", None))

        self.compile_buffer.append({"text": text, "path": path, "ts": datetime.now().isoformat()})

        if auto_adapt or self.config.get("auto_adaptar", False):
            template = self.easy_template.get()
            self.after(500, lambda: self._adapt(template))

    def _prompt_ia_consent(self, callback):
        """Dialogo de consentimiento de privacidad: el analisis con IA ENVIA el
        texto de la transcripcion a servidores de Google/OpenAI. Se pide una vez
        y queda guardado en la config (revocable en Configuracion)."""
        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("🔒 Privacidad y análisis con IA")
        try:
            top.attributes("-topmost", True)
        except Exception:
            pass
        f = self._frame(top, fg_color=C["card"])
        f.pack(fill="both", expand=True, padx=20, pady=20)
        self._lbl(f, "🔒 Aviso de privacidad", font=("Segoe UI", 16, "bold"), text_color=C["accent"]).pack(anchor="w", pady=(0, 8))
        self._lbl(f, "Tus grabaciones y transcripciones se procesan en TU equipo. Sin embargo, el análisis con IA "
                      "(Gemini u OpenAI) ENVÍA el texto de la transcripción a los servidores de Google u OpenAI "
                      "(que lo retienen temporalmente: Gemini hasta 55 días; OpenAI no lo usa para entrenar) "
                      "para generar resúmenes, guías y exámenes.",
                  font=("Segoe UI", 11), text_color=C["muted"], wraplength=560, justify="left").pack(anchor="w", pady=(0, 8))
        self._lbl(f, "Puedes seguir usando AudioClass sin IA (transcripción local) y cambiar esta decisión "
                      "en Configuración en cualquier momento.",
                  font=("Segoe UI", 11), text_color=C["muted"], wraplength=560, justify="left").pack(anchor="w", pady=(0, 12))
        consent = ctk.BooleanVar(value=False)
        if CTK:
            ctk.CTkCheckBox(f, text="Acepto: permito enviar el texto de mis transcripciones a Gemini/OpenAI para análisis con IA",
                            variable=consent, font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", pady=(0, 14))
        else:
            ctk.Checkbutton(f, text="Acepto: permito enviar el texto a Gemini/OpenAI para analisis con IA",
                            variable=consent, bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", pady=(0, 14))

        def go():
            if not consent.get():
                self._msg("warning", "Consentimiento requerido",
                          "Marca la casilla para aceptar el envío a la IA, o cancela para seguir sin análisis con IA.")
                return
            self.config["ia_consent"] = True
            save_config(self.config)
            top.destroy()
            callback()

        row = self._frame(f, fg_color="transparent")
        row.pack(fill="x")
        self._btn(row, "Cancelar (sin IA)", top.destroy, width=170, height=36,
                  fg_color=C.get("warn", "#F59E0B")).pack(side="left", padx=(0, 10))
        self._btn(row, "Aceptar y continuar", go, width=210, height=36, fg_color=C["accent"]).pack(side="right")
        top.transient(self)
        top.grab_set()

    def _adapt(self, template_name):
        if not self.last_text:
            self._msg("warning", "Sin transcripcion", "Primero transcribe un audio.")
            return

        # Consentimiento de privacidad: sin ia_consent no se envia nada a IA.
        if not self.config.get("ia_consent", False):
            self._prompt_ia_consent(lambda: self._run_adapt(template_name))
            return
        self._run_adapt(template_name)

    def _run_adapt(self, template_name):
        prov = self.config.get("adapt_provider", "gemini")
        if prov == "openai":
            key = self.config.get("openai_api_key", "")
            prov_lbl = "OpenAI"
            url = "platform.openai.com/api-keys"
        else:
            key = self.config.get("gemini_api_key", "")
            prov_lbl = "Gemini"
            url = "aistudio.google.com/app/apikey"
        if not key or len(key) < 10:
            self._msg("warning", "Sin API Key",
                      f"Configura tu API Key de {prov_lbl} en Configuracion ({url})")
            return

        info = GeminiAdaptationEngine.TEMPLATES.get(template_name, {})
        self.adapt_info.configure(text=f"{info.get('icon','')} {info.get('desc','')}")

        self._disable_adapt_buttons()
        self.bcancel.configure(state="normal")
        self.lstatus.configure(text=f"Adaptando: {template_name}...", text_color=C["gemini"])
        # Barra propia para la adaptacion (evita que salte de 100% a 33%).
        if CTK: self.pbar.set(0)
        else: self.pbar['value'] = 0
        self.lprog.configure(text=f"Adaptando: {template_name}...")
        self._apptxt(f"\nIniciando adaptacion: {template_name}...\n")

        threading.Thread(target=self._adapt_worker, args=(self.last_text, template_name), daemon=True).start()

    def _adapt_worker(self, text, template_name):
        try:
            def progress(current, total, msg):
                self.q.put(("progress", (current / total, msg)))

            result = self.adapt_engine.adapt(text, template_name, progress_callback=progress)

            if self.cancel:
                self.q.put(("log", "\nCancelado.\n"))
                self.q.put(("status", "Cancelado"))
                self.q.put(("enable", None))
                return

            if "error" in result:
                raise Exception(result["error"])

            adapted = result.get("text", "")
            icon = result.get("icon", "")

            base = os.path.splitext(os.path.basename(self.last_path))[0] if self.last_path else "adaptacion"
            safe_name = template_name.replace(' ', '_').replace('/', '_')
            ap = os.path.join(OUTPUT_DIR, f"{base}_{safe_name}.txt")
            with open(ap, "w", encoding="utf-8") as f:
                f.write(f"{icon} {template_name}\n")
                f.write(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Motor: {result.get('provider', self.adapt_engine.PROVIDER)} {result.get('model', '?')}\n")
                f.write("Contenido generado por IA — puede contener errores. Verifica los datos importantes.\n")
                f.write("="*60 + "\n\n")
                f.write(adapted)

            self.q.put(("adapt_done", (adapted, template_name, icon)))
            self.q.put(("log", f"\n{template_name} generado\nGuardado\n"))
            self.q.put(("status", f"{template_name} listo"))

        except Exception as e:
            self.q.put(("log", f"\nError adaptacion: {e}\n"))
            self.q.put(("status", "Error de adaptacion"))
        finally:
            self.q.put(("enable", None))

    def _disable_adapt_buttons(self):
        for b in self.adapt_buttons.values():
            b.configure(state="disabled")

    def _enable_adapt_buttons(self):
        for b in self.adapt_buttons.values():
            b.configure(state="normal")

    def _set_adapt_text(self, text, title, icon):
        self.adapt_txt.configure(state="normal")
        self.adapt_txt.delete("1.0", "end")
        self.adapt_txt.insert("end", f"{icon} {title}\n{'='*55}\nTexto generado automáticamente — puede contener errores. Verifica los datos importantes.\n\n{text}\n")
        self.adapt_txt.see("end")
        self.adapt_txt.configure(state="disabled")
        self.bsave_adapt.configure(state="normal")

    def _clear_adapt(self):
        self.adapt_txt.configure(state="normal")
        self.adapt_txt.delete("1.0", "end")
        self.adapt_txt.configure(state="disabled")
        self.bsave_adapt.configure(state="disabled")

    def _save_adaptation(self):
        fp = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt"), ("Markdown", "*.md")],
            initialdir=OUTPUT_DIR,
            initialfile=f"adaptacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if not fp: return
        try:
            self.adapt_txt.configure(state="normal")
            content = self.adapt_txt.get("1.0", "end")
            self.adapt_txt.configure(state="disabled")
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            self._set_step(4)
            self._msg("info", "Guardado", f"Guardado en:\n{fp}")
        except Exception as e:
            self._msg("error", "Error", str(e))

    def _pdf_unicode_font(self, pdf):
        """Registra una fuente Unicode para los PDFs y devuelve
        (ttf_ok, full_unicode, hay_negrita).

        - DejaVu (assets/): cobertura Unicode completa (acentos, →, ├, └, …)
          -> full_unicode=True: el texto se pasa tal cual.
        - Fuente del sistema (Windows): cubre acentos pero NO simbolos como
          → o ├ └ -> full_unicode=False: el texto se sanitiza antes.
        - Sin fuente: fuente core "Arial" latin-1 (compatibilidad)."""
        # Rutas candidatas para assets/: junto al script (desarrollo), dentro
        # del bundle de PyInstaller (sys._MEIPASS) y junto al .exe (onedir).
        here = os.path.dirname(os.path.abspath(__file__))
        bases = [here]
        if getattr(sys, "frozen", False):
            bases.append(getattr(sys, "_MEIPASS", here))
            bases.append(os.path.dirname(os.path.abspath(sys.executable)))
        for rel, bold_rel in (("assets/DejaVuSans.ttf", "assets/DejaVuSans-Bold.ttf"),
                              ("assets/fonts/DejaVuSans.ttf", "assets/fonts/DejaVuSans-Bold.ttf")):
            for base in bases:
                p = os.path.join(base, rel)
                if not os.path.exists(p):
                    continue
                try:
                    pdf.add_font("Uni", "", p)
                    pb = os.path.join(base, bold_rel)
                    has_bold = os.path.exists(pb)
                    if has_bold:
                        pdf.add_font("Uni", "B", pb)
                    return True, True, has_bold
                except Exception:
                    continue
        if sys.platform == "win32":
            windir = os.environ.get("WINDIR", r"C:\Windows")
            for n, bn in (("segoeui.ttf", "segoeuib.ttf"), ("calibri.ttf", "calibrib.ttf"),
                          ("arial.ttf", "arialbd.ttf"), ("times.ttf", "timesbd.ttf"),
                          ("georgia.ttf", "georgiab.ttf"), ("verdana.ttf", "verdanab.ttf")):
                p = os.path.join(windir, "Fonts", n)
                if not os.path.exists(p):
                    continue
                try:
                    pdf.add_font("Uni", "", p)
                    pb = os.path.join(windir, "Fonts", bn)
                    has_bold = os.path.exists(pb)
                    if has_bold:
                        pdf.add_font("Uni", "B", pb)
                    return True, False, has_bold
                except Exception:
                    continue
        return False, False, True

    def _pdf_fallback_text(self, t):
        """Prepara el texto para la fuente core latin-1 (sin fuente Unicode):
        sustituye los simbolos tipograficos por ASCII y descarta el resto."""
        for k, v in _PDF_FALLBACK_CHARS.items():
            t = t.replace(k, v)
        return t.encode("latin-1", "replace").decode("latin-1")

    def _fmt_ts(self, sec):
        """Segundos -> mm:ss para timestamps de exportacion."""
        sec = int(sec or 0)
        m, s = divmod(sec, 60)
        return f"{m:02d}:{s:02d}"

    def _export_lines(self, max_len=90):
        """Devuelve (has_ts, lines) para exportar: lineas numeradas con su
        timestamp. Si hay segmentos (transcripcion 'Con tiempos') cada linea
        lleva [mm:ss - mm:ss]; si no, el texto se parte en lineas numeradas
        (has_ts=False)."""
        segs = getattr(self, "last_segments", []) or []
        lines = []
        if segs:
            for s in segs:
                txt = str(s.get("text", "") or "").strip()
                if txt:
                    lines.append((s.get("start", 0), s.get("end", 0), txt))
            if lines:
                return True, lines
        # Sin timestamps: partir el texto en lineas numeradas
        t = (self.last_text or "").replace("\r", "").strip()
        for para in t.split("\n"):
            para = para.strip()
            if not para:
                continue
            while len(para) > max_len:
                cut = para.rfind(" ", 0, max_len)
                if cut < 20:
                    cut = max_len
                lines.append((None, None, para[:cut]))
                para = para[cut:].strip()
            if para:
                lines.append((None, None, para))
        if not lines:
            lines = [(None, None, t)]
        return False, lines

    def _pdf_badge(self, pdf, fam, tit_style, full_unicode):
        """Insignia verde '✓ Revisado por IA' (bloque redondeado, texto
        blanco) centrada en la pagina. Con fuente latin-1 cae al texto plano."""
        try:
            label = "✓ Revisado por IA" if full_unicode else "Revisado por IA"
            pdf.set_font(fam, tit_style, 10)
            bw = pdf.get_string_width(label) + 12
            bx = (210 - bw) / 2
            by = pdf.get_y()
            pdf.set_fill_color(59, 130, 246)  # azul acento (paleta activa)
            try:
                pdf.rect(bx, by, bw, 8, style="F", round_corners=True, corner_radius=4)
            except Exception:
                pdf.rect(bx, by, bw, 8, style="F")
            pdf.set_xy(bx, by + 1)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(bw, 6, label, align="C")
            pdf.set_xy(10, by + 10)
            pdf.set_text_color(30, 30, 30)
        except Exception:
            pass

    def _pdf(self):
        if not self.last_text:
            self._msg("warning", "Sin transcripcion", "Primero transcribe un audio.")
            return
        try:
            from fpdf import FPDF
        except:
            self._msg("error", "Falta fpdf2", "pip install fpdf2")
            return

        fp = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                                           initialdir=OUTPUT_DIR,
                                           initialfile=f"trans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        if not fp: return
        try:
            pdf = FPDF()
            # Fuente Unicode (DejaVu de assets/ o fuente del sistema) para que
            # los acentos y simbolos no salgan como '?'.
            ttf_ok, full_unicode, has_bold = False, False, True
            try:
                ttf_ok, full_unicode, has_bold = self._pdf_unicode_font(pdf)
            except Exception:
                ttf_ok, full_unicode, has_bold = False, False, True
            fam = "Uni" if ttf_ok else "Arial"
            tit_style = "B" if has_bold else ""
            has_ts, lines = self._export_lines()
            model = getattr(self, "last_model", "Whisper")
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font(fam, tit_style, 16)
            # Con fuente latin-1 (sin Unicode) el titulo con acento saldria '?'
            titulo = "Transcripción de Clase" if full_unicode else "Transcripcion de Clase"
            pdf.cell(0, 10, titulo, ln=True, align="C")
            pdf.ln(4)
            pdf.set_font(fam, "", 10)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 6, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
            pdf.cell(0, 6, f"Modelo: {model}", ln=True)
            pdf.cell(0, 6, "Transcripción automática — puede contener errores. No constituye acta oficial.", ln=True)
            pdf.ln(4)
            # Insignia 'Revisado por IA'
            self._pdf_badge(pdf, fam, tit_style, full_unicode)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(6)
            # Cuerpo: numeracion de lineas + timestamps en gris, texto en oscuro
            for i, (st, en, txt) in enumerate(lines, 1):
                if not full_unicode:
                    txt = self._pdf_fallback_text(txt)
                prefix = f"[{i:>3}] "
                if st is not None and en is not None:
                    prefix += f"[{self._fmt_ts(st)} - {self._fmt_ts(en)}] "
                # multi_cell deja el cursor X en el margen derecho: se resetea
                # al margen izquierdo antes de cada linea para que el prefijo
                # de la siguiente iteracion no se desborde ("Not enough space").
                pdf.set_x(pdf.l_margin)
                pdf.set_font(fam, "", 10)
                pdf.set_text_color(110, 110, 110)
                pw = pdf.get_string_width(prefix)
                pdf.cell(pw, 7, prefix)
                pdf.set_font(fam, "", 11)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, txt)
            pdf.output(fp)
            self._set_step(4)
            self._msg("info", "PDF Exportado", f"Guardado en:\n{fp}")
            self.q.put(("log", "PDF exportado\n"))
        except Exception as e:
            self._msg("error", "Error PDF", str(e))

    def _docx_p(self, text, bold=False, size=22, color=None, shading=None, center=False, mono=False):
        """Genera un parrafo WordprocessingML a partir de texto plano.
        El orden de los hijos de w:pPr debe seguir la secuencia del esquema
        OOXML (CT_PPr): w:shd va ANTES de w:spacing y w:jc; si no, Word puede
        marcar el archivo como corrupto o ignorar el sombreado."""
        from xml.sax.saxutils import escape
        rpr = ""
        if bold:
            rpr += "<w:b/>"
        if color:
            rpr += f'<w:color w:val="{color}"/>'
        if mono:
            rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>'
        rpr += f'<w:sz w:val="{size}"/>'
        ppr = ""
        if shading:
            ppr += f'<w:shd w:val="clear" w:color="auto" w:fill="{shading}"/>'
        ppr += '<w:spacing w:after="60"/>' if not mono else '<w:spacing w:line="240" w:lineRule="auto"/>'
        if center:
            ppr += '<w:jc w:val="center"/>'
        return ('<w:p><w:pPr>' + ppr + '</w:pPr><w:r><w:rPr>' + rpr +
                '</w:rPr><w:t xml:space="preserve">' + escape(text) + '</w:t></w:r></w:p>')

    def _docx_heading(self, text, size=24):
        """Encabezado de seccion del informe (negrita, azul marino academico)."""
        return self._docx_p(text, bold=True, size=size, color="0A1F44")

    def _parse_adapt_sections(self, text):
        """Parsea la adaptacion academica de Gemini (formato del prompt
        ACADEMIC_PROMPT) en secciones: resumen ejecutivo, tesis central,
        pilares argumentales, evidencia y datos duros, implicacion y registro
        de filtrado. Soporta dos formatos: encabezado en su propia linea con
        el cuerpo debajo, o encabezado INLINE ("**Resumen Ejecutivo:** texto").
        Si no encuentra encabezados conocidos, devuelve una sola seccion con
        el texto completo."""
        import re
        text = text.replace("\r", "")  # robustez ante CRLF
        HEADERS = [
            ("Resumen Ejecutivo", r"resumen\s+ejecutivo"),
            ("Tesis Central", r"tesis\s+central"),
            ("Pilares Argumentales", r"pilares\s+argumentales"),
            ("Evidencia y Datos Duros", r"evidencia\s+y\s+datos\s+duros"),
            ("Implicación o Aplicabilidad", r"implicaci[oó]n\s+o\s+aplicabilidad"),
            ("Implicación", r"implicaci[oó]n"),
            ("Registro de Filtrado", r"registro\s+de\s+filtrado"),
        ]
        lines = text.split("\n")
        hits = []
        for i, ln in enumerate(lines):
            # Quitar numeracion, viñetas y markdown del inicio; colapsar espacios
            norm = re.sub(r"^[\s\d.\-:()*#•]+", "", ln).strip(" *#\t")
            norm = re.sub(r"\s+", " ", norm).lower()
            for label, pat in HEADERS:
                # re.match ancla la frase al INICIO de la linea: una frase de
                # cuerpo como "La tesis central de la clase es..." no debe
                # crear una seccion falsa a mitad del informe.
                if re.match(pat, norm):
                    if not hits or hits[-1][2] != i:
                        hits.append((label, pat, i))
                    break
        if not hits:
            return [("Análisis Académico", text.strip())]
        sections = []
        for k, (label, pat, idx) in enumerate(hits):
            end = hits[k + 1][2] if k + 1 < len(hits) else len(lines)
            # Cuerpo inline: lo que queda en la MISMA linea despues del label
            # ("**Resumen Ejecutivo:** La clase explica...")
            raw = lines[idx]
            stripped = re.sub(r"^[\s\d.\-:()*#•]+", "", raw).strip()
            m = re.search(pat, stripped, flags=re.IGNORECASE)
            inline = ""
            if m:
                inline = re.sub(r"^[\s:.\-*#•]+", "", stripped[m.end():]).strip()
            body_lines = [x.strip() for x in lines[idx + 1:end] if x.strip()]
            body = "\n".join(filter(None, [inline] + body_lines)).strip()
            sections.append((label, body))
        return sections

    def _export_docx(self):
        """Exporta la transcripcion a DOCX (Word) con timestamps, numeracion,
        insignia 'Revisado por IA' y, si existe una adaptacion de Gemini, un
        INFORME ACADEMICO completo (resumen ejecutivo, tesis, pilares,
        evidencia e implicacion). Genera el .docx directamente con XML (zip +
        WordprocessingML) para no depender de python-docx."""
        if not self.last_text:
            self._msg("warning", "Sin transcripcion", "Primero transcribe un audio.")
            return

        # Adaptacion disponible? (mismo patron que _export_docs)
        adapt_text = ""
        try:
            adapt_text = self.adapt_txt.get("1.0", "end").strip()
        except Exception:
            pass
        include_report = False
        if adapt_text:
            # Quitar el encabezado que _set_adapt_text anade (icono + titulo + ===)
            if "=" * 20 in adapt_text:
                adapt_text = adapt_text.split("=" * 20, 1)[-1].strip()
            if adapt_text.strip():
                include_report = self._ask(
                    "Exportar DOCX",
                    "Incluir el INFORME ACADEMICO de Gemini (resumen, tesis, pilares, evidencia)?\n\n"
                    "Si = informe completo + transcripcion\nNo = solo transcripcion")

        fp = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word", "*.docx")],
                                           initialdir=OUTPUT_DIR,
                                           initialfile=f"trans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx")
        if not fp: return
        try:
            import zipfile
            has_ts, lines = self._export_lines()
            model = getattr(self, "last_model", "Whisper")
            paras = []
            paras.append(self._docx_p("Transcripción de Clase", bold=True, size=28, center=True))
            paras.append(self._docx_p(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Modelo: {model}", color="808080", size=20))
            # Insignia 'Revisado por IA' (verde, texto blanco, centrada)
            paras.append(self._docx_p("✓ Revisado por IA", bold=True, color="FFFFFF", shading="10B981", size=22, center=True))
            paras.append(self._docx_p("Transcripción automática — puede contener errores. No constituye acta oficial.", color="808080", size=17))
            paras.append(self._docx_p(""))

            # Informe academico de Gemini (si el usuario lo pidio)
            if include_report:
                sections = self._parse_adapt_sections(adapt_text)
                paras.append(self._docx_heading("Informe Académico (Gemini)", size=26))
                paras.append(self._docx_p(""))
                for label, body in sections:
                    if not body.strip():
                        continue
                    paras.append(self._docx_p(label, bold=True, size=22, color="B8860B"))
                    for bl in body.split("\n"):
                        bl = bl.strip()
                        if not bl:
                            continue
                        bullet = bl if bl.startswith(("•", "-", "*", "1.", "2.", "3.", "4.", "5.")) else "• " + bl
                        paras.append(self._docx_p(bullet, size=20))
                    paras.append(self._docx_p(""))
                paras.append(self._docx_heading("Transcripción Completa", size=26))
                paras.append(self._docx_p(""))

            # Cuerpo: numeracion + timestamps en monospace
            for i, (st, en, txt) in enumerate(lines, 1):
                prefix = f"[{i:>3}]"
                if st is not None and en is not None:
                    prefix += f" [{self._fmt_ts(st)} - {self._fmt_ts(en)}]"
                paras.append(self._docx_p(f"{prefix}  {txt}", mono=True, size=20))
            doc_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body>' + "".join(paras) +
                '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>'
                '</w:sectPr></w:body></w:document>'
            )
            ct_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>'
            )
            rels_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '</Relationships>'
            )
            with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("[Content_Types].xml", ct_xml)
                z.writestr("_rels/.rels", rels_xml)
                z.writestr("word/document.xml", doc_xml)
            self._set_step(4)
            self._msg("info", "DOCX Exportado", f"Guardado en:\n{fp}")
            self.q.put(("log", "DOCX exportado\n"))
        except Exception as e:
            self._msg("error", "Error DOCX", str(e))

    def _cancel(self):
        self.cancel = True
        self.stop_ev.set()
        # Si el usuario cancela mientras el modelo local carga, la transcripcion
        # pendiente NO debe arrancar sola cuando termine de cargar: se cancela
        # el after agendado y se limpia la peticion pendiente.
        self._pending_trans = None
        if getattr(self, "_pending_after", None):
            try:
                self.after_cancel(self._pending_after)
            except Exception:
                pass
            self._pending_after = None
        self.lstatus.configure(text="Cancelando...", text_color=C["warn"])

    def _trans_ticker(self):
        """Muestra en vivo el tiempo transcurrido + ETA estimado (mejora #3)
        mientras se transcribe, para que el usuario sepa que el proceso avanza
        y cuánto falta (Whisper local tarda por chunk y sin esto parece
        congelado en 'Iniciando transcripcion')."""
        if not self._transcribing:
            return
        try:
            el = int(time.time() - self._trans_start)
            m, s = divmod(el, 60)
            msg = self._trans_msg or "Transcribiendo..."
            eta = ""
            frac = getattr(self, "_trans_frac", 0.0) or 0.0
            if frac > 0.02 and frac < 0.999:
                # ETA = tiempo transcurrido * fraccion restante / fraccion hecha
                rem = int(el * (1.0 - frac) / frac)
                em, es = divmod(rem, 60)
                eta = f"  ·  ETA ~{em:02d}:{es:02d}"
            self.lprog.configure(text=f"{msg}  ·  {m:02d}:{s:02d}{eta}")
            self.after(1000, self._trans_ticker)
        except Exception:
            pass

    def _poll(self):
        try:
            while True:
                mt, d = self.q.get_nowait()

                if mt == "status":
                    self.lstatus.configure(text=d)
                    col = C["ok"] if "Listo" in d else C["err"] if "Error" in d else C["cloud"] if "Cloud" in d else C["gemini"] if "Adapt" in d else C["warn"] if "Proces" in d else C["muted"]
                    self.lstatus.configure(text_color=col)

                elif mt == "log":
                    self._apptxt(d)

                elif mt == "enable":
                    self._transcribing = False
                    self._trans_msg = ""
                    self._trans_frac = 0.0
                    self._last_partial_len = 0
                    self._clear_live()
                    self.btr.configure(state="normal")
                    self.bts.configure(state="normal")
                    self.bpdf.configure(state="normal")
                    self.bdocx.configure(state="normal")
                    self.bdocs.configure(state="normal" if _gdocs_importable() else "disabled")
                    self.bcancel.configure(state="disabled")
                    self._enable_adapt_buttons()

                elif mt == "enable_rec":
                    self.btr.configure(state="normal")
                    self.bts.configure(state="normal")
                    self._set_step(2)
                    self._show_toast("Grabación lista")

                elif mt == "model_ready":
                    self.lmodel.configure(text=f"Whisper {d} listo", text_color=C["ok"])
                    # Transcripcion pendiente: se inicia sola al terminar la carga.
                    # Se guarda el id del after para poder cancelarlo si el
                    # usuario pulsa Cancelar en la ventana de 150 ms.
                    if getattr(self, "_pending_trans", None):
                        ts, aa = self._pending_trans
                        self._pending_trans = None
                        self._pending_after = self.after(150, lambda: self._starttrans(ts, aa))

                elif mt == "model_err":
                    self.lmodel.configure(text=f"Error: {d[:30]}", text_color=C["err"])
                    self._pending_trans = None

                elif mt == "trans_err":
                    self._clear_live()
                    _req = getattr(self, "_last_trans_req", (False, False))
                    self._show_toast("Error de transcripción", kind="err",
                                     retry=lambda: self._starttrans(*_req))

                elif mt == "adapt_test":
                    prov, (ok, msg) = d
                    try:
                        is_g = prov == "gemini"
                        lbl_attr = "gemini_test_lbl" if is_g else "openai_test_lbl"
                        btn_attr = "btn_test_gemini" if is_g else "btn_test_openai"
                        if hasattr(self, lbl_attr) and getattr(self, lbl_attr).winfo_exists():
                            getattr(self, lbl_attr).configure(
                                text=("✓ " if ok else "✗ ") + msg,
                                text_color=C["ok"] if ok else C["err"])
                        if hasattr(self, btn_attr) and getattr(self, btn_attr).winfo_exists():
                            getattr(self, btn_attr).configure(state="normal", text="Probar Conexión")
                    except Exception:
                        pass

                elif mt == "gdoc_connect":
                    ok, msg = d
                    try:
                        if hasattr(self, "gdoc_lbl") and self.gdoc_lbl.winfo_exists():
                            self.gdoc_lbl.configure(
                                text=("✓ " if ok else "✗ ") + msg,
                                text_color=C["ok"] if ok else C["err"])
                        if hasattr(self, "btn_gdoc_connect") and self.btn_gdoc_connect.winfo_exists():
                            self.btn_gdoc_connect.configure(state="normal", text="Conectar con Google")
                    except Exception:
                        pass

                elif mt == "gdoc_done":
                    ok, url = d
                    try:
                        if hasattr(self, "bdocs") and self.bdocs.winfo_exists():
                            if _gdocs_importable():
                                self.bdocs.configure(state="normal", text="🌐 Google Docs")
                            else:
                                self.bdocs.configure(state="disabled", text="🌐 Google Docs (no disponible)")
                    except Exception:
                        pass
                    if ok:
                        self._set_step(4)
                        self._show_toast("Exportado a Google Docs")
                        self.q.put(("log", f"\nDocumento creado en Google Docs:\n{url}\n"))
                        self.q.put(("status", "Exportado a Google Docs"))
                        import webbrowser
                        try:
                            webbrowser.open(url)
                            self._msg("info", "Google Docs", f"Documento creado. Se abrio en tu navegador:\n\n{url}")
                        except Exception:
                            self._msg("info", "Google Docs", f"Documento creado:\n\n{url}")
                    else:
                        self.q.put(("status", "Error al exportar a Google Docs"))
                        self._msg("error", "Google Docs", url)

                elif mt == "trans_done":
                    self._settxt(d)
                    self._set_step(3)
                    self._clear_live()
                    self._show_toast("Transcripción completada", kind="ok")
                    if hasattr(self, "lbadge"):
                        try:
                            self.lbadge.pack(side="right", padx=(0, 14))
                        except Exception:
                            pass

                elif mt == "adapt_done":
                    text, title, icon = d
                    self._set_adapt_text(text, title, icon)
                    self._set_step(4)
                    self._show_toast("Análisis listo")

                elif mt == "mic_lvl":
                    # Medidor de nivel en vivo de la prueba de microfono
                    r = d
                    try:
                        if getattr(self, "mic_test_top", None) is not None and self.mic_test_top.winfo_exists():
                            if CTK:
                                self.mic_lvl_bar.set(min(1.0, r * 10))
                                self.mic_lvl_bar.configure(
                                    progress_color=C["ok"] if r > 0.02 else (C["warn"] if r > 0.005 else C["muted"]))
                            else:
                                self.mic_lvl_bar['value'] = min(100, r * 1000)
                            db = 20 * np.log10(max(r, 1e-6))
                            self.mic_lvl_lbl.configure(text=f"{db:+.0f} dB")
                    except Exception:
                        pass

                elif mt == "mic_result":
                    txt = d
                    try:
                        if getattr(self, "mic_test_top", None) is not None and self.mic_test_top.winfo_exists():
                            ok = txt.startswith("✓")
                            self.mic_state.configure(text="Prueba completada",
                                                     text_color=C["ok"] if ok else C["warn"])
                            self.mic_result.configure(text=txt,
                                                      text_color=C["ok"] if ok else C["warn"])
                    except Exception:
                        pass

                elif mt == "mic_idle":
                    try:
                        if hasattr(self, "btn_mic_test") and self.btn_mic_test.winfo_exists():
                            self.btn_mic_test.configure(state="normal", text="🎙️ Comenzar prueba (8 s)")
                    except Exception:
                        pass

                elif mt == "progress":
                    p, l = d
                    self._trans_msg = l
                    self._trans_frac = p
                    if CTK: self.pbar.set(p)
                    else: self.pbar['value'] = p * 100
                    self.lprog.configure(text=l)

                elif mt == "partial":
                    # Streaming (mejora #3): texto parcial acumulado en vivo.
                    # Throttle: solo redibuja si el texto crecio >= 200 chars
                    # para no recargar el widget en cada chunk menor.
                    if not d or not getattr(self, "_transcribing", False):
                        pass
                    else:
                        prev = getattr(self, "_last_partial_len", 0)
                        if len(d) - prev >= 200:
                            self._stream_live(d)
                            self._last_partial_len = len(d)

                elif mt == "mic_probe":
                    # Resultado del pre-check de microfono (_startrec): si el
                    # nivel es muy debil, _mic_probe_done abre el dialogo de
                    # advertencia con medidor en vivo.
                    self._mic_probe_done(d)

                elif mt == "mic_live":
                    # Medidor en vivo del dialogo "microfono muy bajo": el
                    # usuario ve cuanta senal llega al acercarse al micro, y el
                    # 'Mejor p90' le dice si YA alcanzo la meta.
                    r = d
                    try:
                        if getattr(self, "mic_warn_top", None) is not None and self.mic_warn_top.winfo_exists():
                            col = C["ok"] if r > 0.02 else (C["warn"] if r > 0.005 else C["muted"])
                            if CTK:
                                self.mic_warn_bar.set(min(1.0, r * 10))
                                self.mic_warn_bar.configure(progress_color=col)
                            else:
                                self.mic_warn_bar['value'] = min(100, r * 1000)
                            db = 20 * np.log10(max(r, 1e-6))
                            self.mic_warn_lbl.configure(text=f"{db:+.0f} dB", text_color=col)
                            self._update_mic_warn_best(r)
                    except Exception:
                        pass

                elif mt == "mic_opt_log":
                    # Optimizador de microfono: linea de progreso en su dialogo
                    try:
                        if getattr(self, "mic_opt_top", None) is not None and self.mic_opt_top.winfo_exists():
                            if hasattr(self, "mic_opt_txt"):
                                self.mic_opt_txt.configure(state="normal")
                                self.mic_opt_txt.insert("end", d)
                                self.mic_opt_txt.see("end")
                                self.mic_opt_txt.configure(state="disabled")
                    except Exception:
                        pass

                elif mt == "mic_opt_lvl":
                    # Nivel en vivo de la prueba del optimizador
                    r = d
                    try:
                        if getattr(self, "mic_opt_top", None) is not None and self.mic_opt_top.winfo_exists():
                            if CTK:
                                self.mic_opt_lvl_bar.set(min(1.0, r * 10))
                                self.mic_opt_lvl_bar.configure(
                                    progress_color=C["ok"] if r > 0.02 else (C["warn"] if r > 0.005 else C["muted"]))
                            else:
                                self.mic_opt_lvl_bar['value'] = min(100, r * 1000)
                            db = 20 * np.log10(max(r, 1e-6))
                            self.mic_opt_lvl_lbl.configure(text=f"{db:+.0f} dB")
                    except Exception:
                        pass

                elif mt == "mic_opt_state":
                    # Aviso "HABLA AHORA" durante la prueba del optimizador
                    try:
                        if getattr(self, "mic_opt_state_lbl", None) is not None and self.mic_opt_state_lbl.winfo_exists():
                            self.mic_opt_state_lbl.configure(text=d, text_color=C["err"] if d else C["warn"])
                    except Exception:
                        pass

                elif mt == "mic_opt_done":
                    # Fin del diagnostico/optimizacion: re-habilitar botones y veredicto
                    self._mic_opt_busy = False
                    try:
                        if getattr(self, "mic_opt_top", None) is not None and self.mic_opt_top.winfo_exists():
                            for b in ("btn_mic_opt_diag", "btn_mic_opt_apply"):
                                w = getattr(self, b, None)
                                if w is not None:
                                    try:
                                        if w.winfo_exists():
                                            w.configure(state="normal")
                                    except Exception:
                                        pass
                            if hasattr(self, "mic_opt_state_lbl") and self.mic_opt_state_lbl.winfo_exists():
                                col = C["ok"] if d == "OK" else C["err"]
                                self.mic_opt_state_lbl.configure(text=f"Veredicto: {d}", text_color=col)
                    except Exception:
                        pass

                elif mt == "addhist":
                    self._addhist(d)

        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _fill_gutter(self):
        """Reconstruye los numeros de linea del gutter de transcripcion."""
        try:
            self.txt_gutter.configure(state="normal")
            self.txt_gutter.delete("1.0", "end")
            n = int(self.txt.index("end-1c").split(".")[0]) if self.txt.get("1.0", "end-1c").strip() else 1
            self.txt_gutter.insert("end", "\n".join(str(i) for i in range(1, n + 1)))
            self.txt_gutter.configure(state="disabled")
        except Exception:
            pass

    def _txt_yscroll(self, *a):
        """Sincroniza el gutter con el scroll del area de transcripcion."""
        try:
            self._fill_gutter()
            if a:
                self.txt_gutter.yview_moveto(a[0])
        except Exception:
            pass

    def _apptxt(self, t):
        self.txt.configure(state="normal")
        start = self.txt.index("end-1c")
        self.txt.insert("end", t)
        if getattr(self, "_transcribing", False):
            # Resaltado dorado en vivo mientras la IA transcribe
            self.txt.tag_add("live", start, "end-1c")
        self.txt.see("end")
        self.txt.configure(state="disabled")
        self._txt_yscroll(self.txt.yview()[0])

    def _stream_live(self, t):
        """Muestra el texto parcial en vivo (mejora #3) mientras transcribe:
        reemplaza el contenido con lo transcrito hasta ahora, en dorado, para
        que el usuario vea el texto crecer sin esperar al 100%. Al terminar,
        _settxt() pinta la version final limpia."""
        try:
            self.txt.configure(state="normal")
            self.txt.delete("1.0", "end")
            hdr = "=" * 55 + "\n  TRANSCRIPCION EN VIVO (parcial):\n" + "=" * 55 + "\n\n"
            self.txt.insert("end", hdr)
            self.txt.tag_add("head", "1.0", "end-1c")
            self.txt.insert("end", t + "\n\n⏳ Terminando...")
            # Resaltado dorado de todo el bloque en vivo
            self.txt.tag_add("live", "1.0", "end-1c")
            self.txt.see("end")
            self.txt.configure(state="disabled")
            self._txt_yscroll(self.txt.yview()[0])
        except Exception:
            pass

    def _settxt(self, t):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        hdr = "=" * 55 + "\n  TRANSCRIPCION:\n" + "=" * 55 + "\n\n"
        self.txt.insert("end", hdr)
        self.txt.tag_add("head", "1.0", "end-1c")
        self.txt.insert("end", t + "\n\n" + "=" * 55 + "\n")
        self.txt.see("end")
        self.txt.configure(state="disabled")
        self._txt_yscroll(self.txt.yview()[0])

    def _clear_live(self):
        """Quita el resaltado dorado en vivo al terminar/cancelar la transcripcion."""
        try:
            self.txt.configure(state="normal")
            self.txt.tag_remove("live", "1.0", "end")
            self.txt.configure(state="disabled")
        except Exception:
            pass

    def _copy_trans(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.last_text or "")
            self._show_toast("Transcripción copiada", kind="ok")
        except Exception:
            pass

    def _cleartxt(self):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.configure(state="disabled")
        self._fill_gutter()

    def _bind_shortcuts(self):
        """Atajos de teclado: Espacio play/pausa, Ctrl+R grabar, Ctrl+S guardar,
        Ctrl+E exportar, F1 / '?' ayuda. Se ignoran si el foco esta en un campo
        de texto o entrada (para no interferir al escribir)."""
        try:
            self.bind("<space>", self._kb_play)
            self.bind("<Control-r>", self._kb_record)
            self.bind("<Control-s>", self._kb_save)
            self.bind("<Control-e>", self._kb_export)
            self.bind("<F1>", lambda e: self._open_guide(1))
            self.bind("?", lambda e: None if self._kb_focus_text() else self._open_guide(1))
        except Exception:
            pass

    def _kb_focus_text(self):
        try:
            w = self.focus_get()
            return w is not None and w.winfo_class() in ("Text", "Entry", "ScrolledText", "TEntry", "TCombobox")
        except Exception:
            return False

    def _kb_play(self, e):
        if self._kb_focus_text():
            return None
        if getattr(self, "sel", None):
            self._play()
        return "break"

    def _kb_record(self, e):
        if self._kb_focus_text():
            return None
        self._togglerec()
        return "break"

    def _kb_save(self, e):
        self._show_toast("Proyecto guardado en " + OUTPUT_DIR, kind="ok")
        return "break"

    def _kb_export(self, e):
        if self.last_text:
            self._pdf()
        else:
            self._show_toast("Primero transcribe una clase", kind="warn")
        return "break"

    def _close(self):
        # Cancelar SIEMPRE el evento: cubre tanto la grabacion (recloop) como
        # una transcripcion en curso (el motor consulta stop_ev por chunk).
        # Sin esto, cerrar durante la transcripcion dejaba el pool procesando
        # chunks hasta que el proceso salia (hilos daemon: no cuelga, pero
        # quemaba CPU/RAM innecesariamente).
        self.recording = False
        self.cancel = True
        try:
            self.stop_ev.set()
        except Exception:
            pass
        # Cierre limpio: unir el flusher si quedo vivo y cerrar el archivo
        # ANTES de intentar borrar el temporal (en Windows no se puede borrar
        # un archivo abierto). El flusher cierra el fp en su finally; si el
        # join expira, se cierra aqui para no filtrar el handle.
        flusher = getattr(self, "_flusher_thread", None)
        if flusher is not None and flusher.is_alive():
            flusher.join(timeout=2.0)
        try:
            fp = getattr(self, "_rec_fp", None)
            if fp is not None and not fp.closed:
                fp.close()
        except Exception:
            pass
        # Si _procsave esta leyendo el temporal, el lo borra en su finally;
        # borrarlo aqui le daria un audio vacio (race de cierre rapido).
        if not getattr(self, "_proc_active", False):
            try:
                if os.path.exists(getattr(self, "_rec_raw_path", "")):
                    os.remove(self._rec_raw_path)
                    self._rec_raw_path = ""
            except Exception:
                pass
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Modo headless de autotest (valida la transcripcion local del .exe sin GUI):
    #   AudioClass.exe --selftest-transcribe <audio.wav> <salida.txt> [progreso.txt]
    # Registra ademas los mensajes de progreso (porcentaje + tiempo restante)
    # en un archivo aparte para verificar la barra sin interfaz grafica.
    if "--selftest-transcribe" in sys.argv:
        try:
            i = sys.argv.index("--selftest-transcribe")
            wav_path = sys.argv[i + 1]
            out_path = sys.argv[i + 2] if len(sys.argv) > i + 2 else "selftest_result.txt"
            prog_path = sys.argv[i + 3] if len(sys.argv) > i + 3 else "selftest_progress.txt"
            # Usa el modelo POR DEFECTO de la config (ahora 'base'): el selftest
            # del despliegue valida asi el modelo real que recibe el usuario.
            eng = LocalWhisperEngine(load_config().get("local_model", "base"),
                                     load_config().get("whisper_language", "auto"))
            msgs = []
            def _prog(frac, total, msg):
                msgs.append(f"{int(frac/total*100) if total else 0}% | {msg}")
            res = eng.transcribe(wav_path, timestamps=False, progress_callback=_prog)
            texto = res.get("text", "") or ""
            if "error" in res:
                texto = f"ERROR: {res['error']}"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(texto if texto else "SIN TEXTO")
            with open(prog_path, "w", encoding="utf-8") as f:
                f.write("\n".join(msgs))
            sys.exit(0)
        except Exception as e:
            try:
                with open("selftest_error.txt", "w", encoding="utf-8") as f:
                    f.write(traceback.format_exc())
            except Exception:
                pass
            sys.exit(1)
    try:
        App().mainloop()
    except Exception as e:
        import tkinter.messagebox as mb
        mb.showerror("Error fatal", f"{e}\n\n{traceback.format_exc()}")
