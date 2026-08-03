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

import os, sys, threading, queue, time, warnings, shutil, subprocess, traceback, json, re, textwrap, tempfile, hashlib
from datetime import datetime, timedelta
from pathlib import Path

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
    ctk.set_default_color_theme("blue")
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

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "AudioClass_Recordings")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(OUTPUT_DIR, "audioclass_config.json")

# ── Sistema de diseño académico-profesional ──────────────────────────────────
# Azul marino #0A1F44 · gris pizarra #4A5568 · blanco roto #F5F7FA ·
# dorado académico #D4AF37 · verde éxito #10B981 · bordes #E5E7EB · rojo #EF4444.
PALETTES = {
    "dark": {
        "bg": "#0A1F44", "card": "#12264E", "accent": "#D4AF37",
        "text": "#E8EDF7", "muted": "#8FA3C7", "ok": "#10B981",
        "warn": "#D97706", "err": "#EF4444", "border": "#1E3A6E",
        "cloud": "#8B5CF6", "gemini": "#D4AF37", "mic": "#EF4444",
        "easy": "#10B981", "button": "#1E293B", "academic": "#D4AF37",
        "header": "#0A1F44", "accent_hover": "#B8860B"
    },
    "light": {
        "bg": "#F5F7FA", "card": "#FFFFFF", "accent": "#B8860B",
        "text": "#1A202C", "muted": "#4A5568", "ok": "#0E9F6E",
        "warn": "#B45309", "err": "#DC2626", "border": "#E5E7EB",
        "cloud": "#7C3AED", "gemini": "#B8860B", "mic": "#DC2626",
        "easy": "#0E9F6E", "button": "#E2E8F0", "academic": "#B8860B",
        "header": "#0A1F44", "accent_hover": "#A16207"
    },
}
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
    "local_model": "tiny",
    "cloud_model": "large-v3",
    "gemini_model": "flash",
    "modo_facil": False,
    "modo_guiado": True,
    "auto_adaptar": False,
    "adaptacion_default": "Análisis Académico Profundo",
    "theme": "dark",
    "vu_sensitivity": 0.25,
    "first_run": True
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE DE AUDIO PROFESIONAL (9 ETAPAS)
# ═══════════════════════════════════════════════════════════════════════════════

class AudioPipeline:
    """Pipeline profesional de 9 etapas para clases y conferencias."""

    PROFILES = {
        "Clase Universitaria": {
            "desc": "Auditorios grandes con eco y ruido de fondo",
            "hp_freq": 150, "lp_freq": 7000,
            "noise_prof_sec": 1.0, "noise_decrease": 0.8,
            "comp_th": 0.12, "comp_ratio": 5.0,
            "eq_low": (250, 3.0), "eq_mid": (2500, 5.0), "eq_high": (5000, 2.5),
            "agc_target": 0.20, "vad_threshold": 0.01,
            "min_silence_sec": 0.4, "deesser_freq": 6500, "deesser_db": -4.0,
            "noise_gate": 0.005, "limiter": 0.92
        },
        "Conferencia / Webinar": {
            "desc": "Balanceado para presentaciones online o presenciales",
            "hp_freq": 120, "lp_freq": 8000,
            "noise_prof_sec": 0.8, "noise_decrease": 0.7,
            "comp_th": 0.15, "comp_ratio": 4.0,
            "eq_low": (300, 2.5), "eq_mid": (2800, 4.0), "eq_high": (5500, 2.0),
            "agc_target": 0.22, "vad_threshold": 0.008,
            "min_silence_sec": 0.3, "deesser_freq": 7000, "deesser_db": -3.0,
            "noise_gate": 0.004, "limiter": 0.94
        },
        "Podcast / Entrevista": {
            "desc": "Voz cálida y profesional, mínimo procesamiento",
            "hp_freq": 80, "lp_freq": 8500,
            "noise_prof_sec": 0.6, "noise_decrease": 0.6,
            "comp_th": 0.18, "comp_ratio": 3.0,
            "eq_low": (200, 3.5), "eq_mid": (2200, 3.0), "eq_high": (6000, 3.5),
            "agc_target": 0.25, "vad_threshold": 0.006,
            "min_silence_sec": 0.25, "deesser_freq": 6000, "deesser_db": -2.5,
            "noise_gate": 0.003, "limiter": 0.95
        },
        "Cerca del Micrófono": {
            "desc": "Estudio o micrófono de solapa, calidad máxima",
            "hp_freq": 80, "lp_freq": 9000,
            "noise_prof_sec": 0.5, "noise_decrease": 0.5,
            "comp_th": 0.20, "comp_ratio": 2.5,
            "eq_low": (180, 2.0), "eq_mid": (2500, 2.5), "eq_high": (5000, 1.5),
            "agc_target": 0.28, "vad_threshold": 0.005,
            "min_silence_sec": 0.2, "deesser_freq": 7500, "deesser_db": -2.0,
            "noise_gate": 0.002, "limiter": 0.96
        }
    }

    def __init__(self, profile_name="Clase Universitaria", fast_mode=False, use_vad=True):
        self.profile = self.PROFILES.get(profile_name, self.PROFILES["Clase Universitaria"])
        self.fast_mode = fast_mode
        self.use_vad = use_vad
        self.p = self.profile

    def process(self, audio, progress_callback=None):
        audio = audio.astype(np.float64)
        steps = 9 if not self.fast_mode else 5
        step = 0

        def report(name):
            nonlocal step
            step += 1
            if progress_callback:
                progress_callback(step, steps, name)

        rms = np.sqrt(np.mean(audio**2))
        if rms > 0:
            audio *= 0.18 / rms
        report("Normalización de nivel")

        sos_hp = signal.butter(8, self.p["hp_freq"], btype='high', fs=SAMPLE_RATE, output='sos')
        audio = signal.sosfilt(sos_hp, audio)
        report(f"Filtro pasa-altas ({self.p['hp_freq']}Hz)")

        # Limitar la frecuencia de corte al maximo valido (fs/2 - 1): los
        # perfiles con lp_freq >= 8000 romperian butter() con un ValueError
        # (Wn debe ser 0 < Wn < fs/2).
        lp_freq = min(self.p["lp_freq"], SAMPLE_RATE // 2 - 1)
        sos_lp = signal.butter(8, lp_freq, btype='low', fs=SAMPLE_RATE, output='sos')
        audio = signal.sosfilt(sos_lp, audio)
        report(f"Filtro pasa-bajas ({lp_freq}Hz)")

        if not self.fast_mode:
            try:
                import noisereduce as nr
                ns = int(self.p["noise_prof_sec"] * SAMPLE_RATE)
                npf = audio[:ns] if len(audio) > ns else audio[:max(1, len(audio)//10)]
                audio = nr.reduce_noise(
                    y=audio, y_noise=npf, sr=SAMPLE_RATE,
                    prop_decrease=self.p["noise_decrease"], stationary=False,
                    n_fft=1024, n_jobs=1
                )
                report("Reducción de ruido avanzada")
            except Exception:
                report("Reducción de ruido (no disponible)")
        else:
            report("Modo rápido — sin reducción de ruido")

        audio = self._noise_gate(audio, self.p["noise_gate"])
        report("Noise Gate")

        audio = self._deesser(audio, self.p["deesser_freq"], self.p["deesser_db"])
        report("De-esser (sibilancias)")

        audio = self._multiband_comp(audio)
        report("Compresión multibanda")

        audio = self._eq(audio, self.p["eq_low"][0], self.p["eq_low"][1], Q=1.8)
        audio = self._eq(audio, self.p["eq_mid"][0], self.p["eq_mid"][1], Q=2.2)
        audio = self._eq(audio, self.p["eq_high"][0], self.p["eq_high"][1], Q=2.0)
        report("Ecualización de voz (3 bandas)")

        audio = self._agc_vad_limiter(audio)
        report("AGC + VAD + Limitador final")

        return audio.astype(np.float32)

    def _noise_gate(self, audio, threshold):
        mask = np.abs(audio) < threshold
        gated = audio.copy()
        gated[mask] *= 0.05
        return gated

    def _deesser(self, audio, freq, db_reduction):
        w0 = 2 * np.pi * freq / SAMPLE_RATE
        Q = 3.0
        alpha = np.sin(w0) / (2 * Q)
        A = 10**(db_reduction / 40)
        b0, b1, b2 = 1 + alpha*A, -2*np.cos(w0), 1 - alpha*A
        a0, a1, a2 = 1 + alpha/A, -2*np.cos(w0), 1 - alpha/A
        if abs(a0) < 1e-10:
            return audio
        return signal.lfilter(np.array([b0,b1,b2])/a0, np.array([a0,a1,a2])/a0, audio)

    def _multiband_comp(self, audio):
        sos_low = signal.butter(4, 500, btype='low', fs=SAMPLE_RATE, output='sos')
        sos_mid = signal.butter(4, [500, 4000], btype='band', fs=SAMPLE_RATE, output='sos')
        sos_high = signal.butter(4, 4000, btype='high', fs=SAMPLE_RATE, output='sos')

        low = signal.sosfilt(sos_low, audio)
        mid = signal.sosfilt(sos_mid, audio)
        high = signal.sosfilt(sos_high, audio)

        low = self._comp_band(low, self.p["comp_th"] * 1.2, self.p["comp_ratio"] * 0.8)
        mid = self._comp_band(mid, self.p["comp_th"], self.p["comp_ratio"])
        high = self._comp_band(high, self.p["comp_th"] * 0.8, self.p["comp_ratio"] * 1.2)

        return low + mid + high

    def _comp_band(self, audio, th, ratio):
        c = np.copy(audio)
        mask = np.abs(audio) > th
        if np.any(mask):
            c[mask] = np.sign(audio[mask]) * (th + (np.abs(audio[mask]) - th) / ratio)
            gain = 1.0 / (th + (1.0 - th) / ratio)
            c *= gain
        return c

    def _eq(self, audio, fc, gdb, Q=2.0):
        w0 = 2 * np.pi * fc / SAMPLE_RATE
        alpha = np.sin(w0) / (2 * Q)
        A = 10**(gdb / 40)
        b0, b1, b2 = 1 + alpha*A, -2*np.cos(w0), 1 - alpha*A
        a0, a1, a2 = 1 + alpha/A, -2*np.cos(w0), 1 - alpha/A
        if abs(a0) < 1e-10:
            return audio
        return signal.lfilter(np.array([b0,b1,b2])/a0, np.array([a0,a1,a2])/a0, audio)

    def _frame_rms(self, audio, window, hop, batch=16384):
        """RMS de cada trama (inicios 0, hop, 2*hop, ... < len-window) en UNA
        sola pasada vectorizada con sliding_window_view, procesada por bloques
        para no duplicar memoria en clases largas (una clase de 3h genera
        ~540k tramas). Resultado identico al bucle por trama original."""
        n = len(audio)
        if n <= window:
            return np.zeros(0, dtype=np.float64)
        sw = np.lib.stride_tricks.sliding_window_view(audio, window)[0 : n - window : hop]
        out = np.empty(sw.shape[0], dtype=np.float64)
        for b in range(0, sw.shape[0], batch):
            rows = sw[b:b + batch]
            out[b:b + rows.shape[0]] = np.sqrt(np.mean(rows * rows, axis=1))
        return out

    def _agc_vad_limiter(self, audio):
        window = int(0.04 * SAMPLE_RATE)
        hop = window // 2
        output = np.zeros_like(audio)
        window_fn = np.hanning(window)

        # RMS de todas las tramas en UNA sola pasada vectorizada (antes se
        # recorria el audio DOS veces por trama: una para estimar el umbral
        # adaptativo y otra para aplicar la ganancia).
        frames_rms = self._frame_rms(audio, window, hop)
        if len(frames_rms) > 0:
            # Umbral VAD adaptativo al piso de ruido del ambiente: se estima
            # con las tramas mas silenciosas del audio (percentil 10, que suele
            # caer en las pausas entre frases). Asi un ruido de fondo constante
            # (ventilador, aire acondicionado) NO se trata como voz y no se
            # re-amplifica entre frases: solo se amplifica lo que supera
            # claramente el ruido.
            noise_floor = float(np.percentile(frames_rms, 10))
            # Tope anti-caso-limite: si el ventilador es tan ruidoso que el piso
            # (p10) se acerca al nivel de la voz, el factor fijo x3.0 comeria la
            # voz suave (las tramas entre el piso y el umbral se atenuarian x0.05
            # y, peor aun, _remove_silences las borraria de la salida). El tope
            # actua cuando hay indicios de habla real (p90/p10 > 2.0; el
            # solo-ruido da ~1.5) y el umbral viejo quedaria por encima del nivel
            # de habla: entonces el umbral baja al 60% del nivel de habla (p90),
            # rescatando las frases suaves sin amplificar el ruido de fondo.
            speech_ref = float(np.percentile(frames_rms, 90))
            spread = (speech_ref / noise_floor) if noise_floor > 0 else 0.0
            if spread > 2.0 and noise_floor * 3.0 > speech_ref * 0.6:
                vad_thr = max(self.p["vad_threshold"], speech_ref * 0.6)
            else:
                vad_thr = max(self.p["vad_threshold"], noise_floor * 3.0)
            silence_thr = max(self.p["vad_threshold"] * 0.4, noise_floor * 0.5)
        else:
            vad_thr = self.p["vad_threshold"]
            silence_thr = self.p["vad_threshold"] * 0.4

        for k, i in enumerate(range(0, len(audio) - window, hop)):
            chunk = audio[i:i + window]
            rms = float(frames_rms[k])

            if rms > vad_thr:
                target = self.p["agc_target"]
                gain = target / rms if rms > 0 else 1.0
                gain = min(gain, 10.0)
                output[i:i + window] += chunk * gain * window_fn
            else:
                output[i:i + window] += chunk * 0.05 * window_fn

        output = np.clip(output, -self.p["limiter"], self.p["limiter"])

        if self.use_vad:
            output = self._remove_silences(output, silence_thr)

        return output

    def _remove_silences(self, audio, silence_threshold=None):
        """Recorta silencios largos. silence_threshold se puede pasar como
        umbral adaptativo (estimado del piso de ruido); si no, usa el fijo."""
        window = int(0.02 * SAMPLE_RATE)
        threshold = silence_threshold if silence_threshold is not None else self.p["vad_threshold"] * 0.4
        max_silent = int(self.p["min_silence_sec"] * SAMPLE_RATE / window)

        segments = []
        current = []
        silent_frames = 0

        for i in range(0, len(audio), window):
            chunk = audio[i:i+window]
            rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0

            if rms > threshold:
                if silent_frames > 0 and silent_frames <= max_silent:
                    current.append(np.zeros(window))
                silent_frames = 0
                current.append(chunk)
            else:
                silent_frames += 1
                if silent_frames > max_silent:
                    if current:
                        segments.append(np.concatenate(current))
                        current = []
                    silent_frames = 0

        if current:
            segments.append(np.concatenate(current))

        return np.concatenate(segments) if segments else audio


# ═══════════════════════════════════════════════════════════════════════════════
# MOTORES DE TRANSCRIPCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class LocalWhisperEngine:
    """Motor de transcripción local con tiny/base/small."""

    def __init__(self, model_name="tiny"):
        self.model_name = model_name
        self.model = None
        self.loading = False
        self.ready = False
        self.error = None

    def _resolve_model(self):
        """Devuelve la ruta del modelo empaquetado en el bundle (modo frozen,
        para funcionar sin internet) o el nombre del modelo (modo desarrollo,
        donde whisper usa su cache o lo descarga la primera vez)."""
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
            for name in (self.model_name, "tiny"):
                p = os.path.join(base, "models", f"{name}.pt")
                if os.path.exists(p):
                    # Si el modelo pedido no va empaquetado, cargamos tiny y
                    # actualizamos self.model_name para que el resultado no
                    # reporte un modelo distinto del realmente cargado.
                    self.model_name = name
                    return p
        return self.model_name

    def load(self, callback=None):
        if self.loading or self.ready:
            return
        self.loading = True

        def _load():
            try:
                import whisper
                self.model = whisper.load_model(self._resolve_model())
                self.ready = True
                if callback:
                    callback("ready", self.model_name)
            except Exception as e:
                self.error = str(e)
                if callback:
                    callback("error", str(e))
            finally:
                self.loading = False

        threading.Thread(target=_load, daemon=True).start()

    def transcribe(self, audio_path, timestamps=False, cancel_event=None, progress_callback=None):
        import whisper
        if self.model is None:
            self.model = whisper.load_model(self._resolve_model())

        sr, data = wavfile.read(audio_path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        else:
            data = data.astype(np.float32)

        if len(data.shape) > 1:
            data = np.mean(data, axis=1)
        if sr != SAMPLE_RATE:
            # .astype(np.float32): signal.resample devuelve float64 y Whisper
            # (torch.from_numpy) lo acepta pero a coste doble en clases largas.
            data = signal.resample(data, int(len(data) * SAMPLE_RATE / sr)).astype(np.float32)

        chunk_samples = int(30 * SAMPLE_RATE)
        chunks = [data[i:i+chunk_samples] for i in range(0, len(data), chunk_samples)]
        total = len(chunks)
        if total == 0:
            return {"text": "", "segments": [], "model": self.model_name,
                    "device": "cpu", "chunks": 0}

        # ── Procesamiento PARALELO de chunks (ThreadPoolExecutor) ────────────
        # Un worker por nucleo de CPU. openai-whisper 20250625 NO es thread-safe
        # para transcribe() concurrente sobre el MISMO modelo (instala hooks de
        # kv_cache sobre el modulo compartido -> KeyError), asi que cada worker
        # carga SU PROPIA copia del modelo (deepcopy aísla el cache interno de
        # whisper). Cada copia usa UN solo hilo de torch (set_num_threads(1))
        # para evitar oversubscription: si 8 workers usaran los 8 hilos de torch
        # por defecto, el SO alternaria 64 hilos en 8 nucleos y el total
        # tardaria MAS que en secuencial. Presupuesto de RAM: ~1.5 GB maximo en
        # copias del modelo.
        cores = os.cpu_count() or 4
        mb = {"tiny": 75, "base": 142, "small": 466}.get(self.model_name, 150)
        by_mem = max(1, min(8, int(1536 / mb)))
        workers = max(1, min(cores, total, by_mem))
        # Nota de calidad: en paralelo cada chunk se transcribe de forma
        # independiente (condition_on_previous_text=False). Whisper solo
        # condiciona segmentos DENTRO de la misma llamada; en chunks de 30s
        # (1-3 segmentos) la perdida es despreciable y el initial_prompt
        # academico sigue anclando el estilo en cada chunk.

        PROMPT = (
            "Esta es una transcripción de una clase universitaria o conferencia académica en español. "
            "El orador principal es el docente o conferencista. "
            "Ignora murmullos de fondo, interrupciones breves y preguntas sin respuesta del docente. "
            "Preserva datos duros: números, fechas, dosis, nomenclaturas técnicas y definiciones literales exactas. "
            "Transcribe fielmente solo lo dicho por el orador principal."
        )

        def _transcribe_with(mdl, chunk, use_cond):
            # Se pasa el array float32 directamente a Whisper (sin escribir
            # WAV temporal): evita depender de ffmpeg y funciona offline.
            return mdl.transcribe(
                chunk, language="es", task="transcribe",
                fp16=False, verbose=False,
                condition_on_previous_text=use_cond,
                initial_prompt=PROMPT
            )

        if workers == 1:
            # ── Camino secuencial (1 chunk, 1 nucleo o modelo grande) ─────────
            if self.model is None:
                import whisper
                self.model = whisper.load_model(self._resolve_model())

            parts, segs, ct = [], [], 0.0
            chunk_times = []   # tiempos reales -> media movil (ultimos 3)
            est_dur = 30.0     # seed del 1er chunk: 1x su duracion (30s)
            for i, chunk in enumerate(chunks, 1):
                if cancel_event and cancel_event.is_set():
                    return {"cancelled": True}
                if progress_callback:
                    progress_callback(i - 1, total, f"Procesando chunk {i}/{total}...")

                # Whisper no reporta progreso dentro del chunk: un hilo auxiliar
                # estima el avance con la media movil del tiempo por chunk.
                stop = threading.Event()
                t0 = time.time()

                def _report(i=i, t0=t0, est=est_dur, stop=stop):
                    while not stop.is_set():
                        el = time.time() - t0
                        frac = min(el / est, 0.95) if est > 0 else 0.0
                        if stop.is_set():
                            break
                        if progress_callback:
                            pct = int((i - 1 + frac) / total * 100)
                            rem = max(0, int(est - el))
                            progress_callback(i - 1 + frac, total,
                                              f"Chunk {i}/{total} · {pct}% · ~{rem}s rest")
                        stop.wait(0.25)

                rthread = threading.Thread(target=_report, daemon=True)
                rthread.start()

                try:
                    result = _transcribe_with(self.model, chunk, True)
                finally:
                    stop.set()
                    rthread.join(timeout=1.0)

                chunk_times.append(time.time() - t0)
                est_dur = float(np.mean(chunk_times[-3:]))

                if progress_callback:
                    progress_callback(i, total, f"Chunk {i}/{total} listo")

                if result.get("text"):
                    parts.append(result["text"].strip())
                if timestamps and "segments" in result:
                    for s in result["segments"]:
                        sc = dict(s)
                        sc["start"] += ct
                        sc["end"] += ct
                        segs.append(sc)
                ct += 30

            return {
                "text": " ".join(parts),
                "segments": segs,
                "model": self.model_name,
                "device": "cpu",
                "chunks": total,
                "workers": 1
            }

        # ── Camino PARALELO: un modelo Whisper POR WORKER (thread-local) ──────
        import torch
        prev_threads = torch.get_num_threads()
        torch.set_num_threads(1)

        import copy
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}     # indice -> resultado (acceso bajo lock)
        started = {}     # indice -> t0 real de inicio del worker
        times = []       # tiempos reales por chunk -> media movil (ultimos 3)
        est = [30.0]     # seed del 1er chunk: 1x su duracion (30s)
        last_num = [0.0] # maximo reportado: la barra nunca retrocede
        lock = threading.Lock()
        stop = threading.Event()
        _local = threading.local()

        def _init_worker(path):
            # Nota: los hilos del ThreadPoolExecutor ya son daemon en CPython
            # (se marcan antes de start() en concurrent.futures.thread), asi
            # que la app nunca se cuelga al cerrar por chunks en curso: el
            # proceso sale limpio sin hacer join() de los workers.
            # (NO intentar self.current_thread().daemon=True aqui: el hilo ya
            # esta iniciado y lanza RuntimeError que rompe el pool entero.)
            import whisper
            # deepcopy: esta copia queda aislada de cualquier cache interno de
            # whisper (los hooks de kv_cache se instalan sobre el modelo
            # compartido y romperian la transcripcion concurrente).
            _local.model = copy.deepcopy(whisper.load_model(path))

        def _report():
            # Whisper no reporta progreso dentro del chunk: este hilo estima el
            # avance global = chunks terminados + fraccion estimada de los que
            # siguen corriendo (media movil del tiempo por chunk). max(last_num)
            # sujeta el avance para que la barra NUNCA retroceda.
            while not stop.is_set():
                with lock:
                    done = len(results)
                    running = [(i, t0) for i, t0 in started.items() if i not in results]
                now = time.time()
                frac_sum = 0.0
                for _i, t0 in running:
                    frac_sum += min((now - t0) / est[0], 0.95) if est[0] > 0 else 0.0
                # Lectura/escritura de last_num bajo lock: ambos hilos (este y
                # el bucle principal) la comparten, y asi la monotonia es
                # estricta sin micro-carreras.
                with lock:
                    num = max(last_num[0], done + frac_sum)
                    last_num[0] = num
                pct = int(num / total * 100)
                rem = max(0, int((total - done) / workers * est[0]))
                if progress_callback:
                    progress_callback(num, total,
                                      f"⚡ {workers} núcleos · {done}/{total} chunks · {pct}% · ~{rem}s rest")
                stop.wait(0.25)

        def _transcribe_one(idx, chunk):
            with lock:
                started[idx] = time.time()
            return idx, _transcribe_with(_local.model, chunk, False)

        pool = ThreadPoolExecutor(max_workers=workers,
                                  initializer=_init_worker,
                                  initargs=(self._resolve_model(),))
        futures = [pool.submit(_transcribe_one, i, ch) for i, ch in enumerate(chunks)]
        rthread = threading.Thread(target=_report, daemon=True)
        rthread.start()

        cancelled = False
        error = None
        try:
            for fut in as_completed(futures):
                if cancel_event and cancel_event.is_set():
                    cancelled = True
                    break
                try:
                    idx, result = fut.result()
                except Exception as e:
                    error = e
                    break
                with lock:
                    started_t0 = started.get(idx)
                    results[idx] = result
                if started_t0 is not None:
                    with lock:
                        times.append(time.time() - started_t0)
                        est[0] = float(np.mean(times[-3:]))
                if progress_callback:
                    with lock:
                        done = len(results)
                        # Clamp al maximo reportado: el reporter puede haber
                        # avanzado hasta done + 0.95 x chunks en curso, y un
                        # mensaje con done entero haria la barra RETROCEDER.
                        num = max(last_num[0], float(done))
                        last_num[0] = num
                    progress_callback(num, total, f"{done}/{total} chunks listos")
        finally:
            stop.set()
            rthread.join(timeout=1.0)
            if cancelled or error:
                pool.shutdown(wait=False, cancel_futures=True)
            else:
                pool.shutdown(wait=True)
            torch.set_num_threads(prev_threads)

        if cancelled:
            return {"cancelled": True}
        if error:
            raise error

        # Reconstruir en ORDEN original (los chunks terminan desordenados)
        parts, segs = [], []
        for i in range(total):
            r = results.get(i)
            if not r:
                continue
            if r.get("text"):
                parts.append(r["text"].strip())
            if timestamps and "segments" in r:
                for s in r["segments"]:
                    sc = dict(s)
                    sc["start"] += i * 30.0
                    sc["end"] += i * 30.0
                    segs.append(sc)

        return {
            "text": " ".join(parts),
            "segments": segs,
            "model": self.model_name,
            "device": "cpu",
            "chunks": total,
            "workers": workers
        }


class CloudColabEngine:
    """Motor de transcripción vía Google Colab (Medium/Large)."""

    def __init__(self, url="", api_key="audioclass"):
        self.url = url.rstrip("/") if url else ""
        self.api_key = api_key
        self.connected = False

    def test_connection(self):
        if not self.url:
            return False, "Sin URL configurada"
        try:
            import requests
            r = requests.get(f"{self.url}/status", timeout=10)
            if r.status_code == 200:
                data = r.json()
                return True, f"Conectado: {data.get('model','?')} en {data.get('device','?')}"
            return False, f"Error HTTP {r.status_code}"
        except Exception as e:
            return False, str(e)

    def transcribe(self, audio_path, timestamps=False, cancel_event=None, progress_callback=None):
        import requests
        endpoint = f"{self.url}/transcribe_ts" if timestamps else f"{self.url}/transcribe"

        if progress_callback:
            progress_callback(1, 3, "Subiendo audio a Colab...")

        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
            data = {"key": self.api_key}

            if progress_callback:
                progress_callback(2, 3, "Transcribiendo en GPU...")

            r = requests.post(endpoint, files=files, data=data, timeout=300)

        if cancel_event and cancel_event.is_set():
            return {"cancelled": True}

        if r.status_code == 200:
            result = r.json()
            result["device"] = result.get("device", "gpu")
            result["model"] = result.get("model", "cloud")
            return result
        else:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}


# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE ADAPTACIÓN INTELIGENTE (GEMINI API)
# ═══════════════════════════════════════════════════════════════════════════════

class GeminiAdaptationEngine:
    """Adapta transcripciones en bruto a formatos útiles usando Gemini API."""

    # Prompt académico de élite proporcionado por el usuario
    ACADEMIC_PROMPT = """Actúa como un filtro cognitivo académico especializado en minería de textos con múltiples hablantes. Tu misión es procesar una transcripción densa de una clase, identificando al orador principal por su volumen de texto y autoridad temática, e ignorando totalmente las voces secundarias —como interrupciones, murmullos o preguntas irrelevantes— a menos que el orador principal retome explícitamente una pregunta para desarrollar un concepto; en ese caso, extraerás únicamente la respuesta del orador. Debes aplicar dos reglas de oro para garantizar la fidelidad absoluta: primero, tienes prohibido alucinar, lo que significa que no puedes añadir ejemplos, definiciones ni datos que no estén escritos textualmente en la transcripción; segundo, debes preservar los datos duros, por lo que si el orador menciona números, fechas, dosis, nomenclaturas técnicas o definiciones literales, los transcribirás tal cual, sin parafrasearlos. En cuanto a la extensión, el resumen ejecutivo no debe exceder las doscientas palabras, lo que equivale aproximadamente a mil cuatrocientos caracteres, muy por debajo del límite de dos mil, lo que te da un margen seguro para cumplir siempre la restricción. El formato de salida debe ser exclusivamente el siguiente: en primer lugar, redacta un resumen ejecutivo en un párrafo único, cohesivo y ultracompacto, que narre la evolución del tema principal desde la introducción hasta el cierre del orador. En segundo lugar, presenta una extracción estructurada que contenga cuatro elementos obligatorios: la tesis central, expresada en una frase concisa que capture el propósito global de la clase; los pilares argumentales, que serán una lista de máximo cinco ideas medulares que sostienen dicha tesis; la evidencia y datos duros, donde citarás el ejemplo, cifra o definición textual más relevante que el docente usó como ancla; y la implicación o aplicabilidad, donde resumirás en una línea cualquier mención del docente sobre utilidad en la vida real o en el campo profesional. Por último, deberás incluir un registro de filtrado, enumerando en una sola línea los tipos de comentarios que descartaste, como anécdotas personales sin valor teórico, murmullos de fondo o preguntas no respondidas, para evidenciar que aplicaste correctamente el filtro. Una vez recibidas estas instrucciones, procede con el análisis de la transcripción que se te proporcionará a continuación."""

    TEMPLATES = {
        "Análisis Académico Profundo": {
            "prompt": ACADEMIC_PROMPT + "\n\nTRANSCRIPCIÓN:\n{TEXT}\n\nANÁLISIS ACADÉMICO:",
            "icon": "🎓",
            "desc": "Filtro cognitivo con tesis, pilares, evidencia y registro de filtrado",
            "max_tokens": 4096,
            "temperature": 0.1
        },
        "Resumen Ejecutivo": {
            "prompt": "Analiza la siguiente transcripción de una clase o conferencia y genera un RESUMEN EJECUTIVO profesional.\n\nInstrucciones:\n- Extrae los 5-7 puntos más importantes\n- Usa bullets claros y concisos\n- Incluye conclusiones clave\n- Máximo 500 palabras\n- Formato: Markdown simple\n\nTranscripción:\n{TEXT}\n\nResumen Ejecutivo:",
            "icon": "📋",
            "desc": "Puntos clave y conclusiones",
            "max_tokens": 2048,
            "temperature": 0.3
        },
        "Guía de Estudio": {
            "prompt": "Convierte la siguiente transcripción de clase en una GUÍA DE ESTUDIO estructurada para estudiantes.\n\nInstrucciones:\n1. Identifica el tema principal y subtemas\n2. Crea secciones con títulos claros\n3. Destaca definiciones importantes en negrita\n4. Lista fórmulas, fechas o datos clave\n5. Añade una sección de 'Puntos Clave para Recordar'\n6. Formato: Markdown con headers (# ## ###)\n\nTranscripción:\n{TEXT}\n\nGuía de Estudio:",
            "icon": "📚",
            "desc": "Secciones, definiciones y puntos clave",
            "max_tokens": 4096,
            "temperature": 0.2
        },
        "Flashcards (Preguntas)": {
            "prompt": "Genera FLASHCARDS de estudio a partir de esta transcripción de clase.\n\nInstrucciones:\n- Crea 10-15 preguntas y respuestas\n- Cada flashcard debe ser concisa\n- Formato exacto:\n  Q: [Pregunta]\n  A: [Respuesta]\n  ---\n- Cubre los conceptos más importantes\n\nTranscripción:\n{TEXT}\n\nFlashcards:",
            "icon": "🎯",
            "desc": "Preguntas y respuestas para memorizar",
            "max_tokens": 4096,
            "temperature": 0.2
        },
        "Preguntas de Examen": {
            "prompt": "Genera PREGUNTAS DE EXAMEN tipo test a partir de esta transcripción.\n\nInstrucciones:\n- 10 preguntas de opción múltiple (A, B, C, D)\n- 3 preguntas de respuesta corta\n- 2 preguntas de desarrollo\n- Indica la respuesta correcta para las de opción múltiple\n- Formato claro y ordenado\n\nTranscripción:\n{TEXT}\n\nPreguntas de Examen:",
            "icon": "❓",
            "desc": "Test, respuesta corta y desarrollo",
            "max_tokens": 4096,
            "temperature": 0.2
        },
        "Mapa Conceptual (Texto)": {
            "prompt": "Genera un MAPA CONCEPTUAL en formato texto jerárquico a partir de esta transcripción.\n\nInstrucciones:\n- Usa indentación con tabs para mostrar jerarquía\n- Concepto principal al nivel 0\n- Subconceptos indentados\n- Relaciones claras entre ideas\n- Formato:\n  CONCEPTO PRINCIPAL\n    ├─ Subconcepto A\n    │  ├─ Detalle 1\n    │  └─ Detalle 2\n    └─ Subconcepto B\n\nTranscripción:\n{TEXT}\n\nMapa Conceptual:",
            "icon": "🗺️",
            "desc": "Jerarquía visual en texto",
            "max_tokens": 4096,
            "temperature": 0.2
        },
        "Texto Limpio (Corrección)": {
            "prompt": "Corrige y limpia la siguiente transcripción en bruto.\n\nInstrucciones:\n- Corrige errores gramaticales y ortográficos obvios\n- Elimina repeticiones ('eh', 'mmm', 'este...')\n- Mejora la puntuación\n- Divide en párrafos lógicos\n- Mantén TODO el contenido, no resumas\n- Formato: texto corrido y limpio\n\nTranscripción:\n{TEXT}\n\nTexto Corregido:",
            "icon": "✨",
            "desc": "Corrección de errores y muletillas",
            "max_tokens": 4096,
            "temperature": 0.1
        },
        "Cronología / Timeline": {
            "prompt": "Extrae una CRONOLOGÍA o timeline de eventos, fechas o procesos mencionados en esta transcripción.\n\nInstrucciones:\n- Lista en orden cronológico\n- Formato: [Fecha/Evento] → Descripción\n- Si no hay fechas exactas, usa orden lógico (primero, luego, después, finalmente)\n- Destaca causas y consecuencias\n\nTranscripción:\n{TEXT}\n\nCronología:",
            "icon": "📅",
            "desc": "Orden cronológico de eventos",
            "max_tokens": 2048,
            "temperature": 0.2
        }
    }

    # Modelos Gemini vigentes (gemini-1.5 fue retirado en 2025)
    # flash = 2.0 (menor coste/latencia) | pro = 2.5 (maxima calidad)
    GEMINI_MODELS = {
        "flash": "gemini-2.0-flash",
        "pro": "gemini-2.5-pro",
    }

    def __init__(self, api_key="", model="flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _model_name(self):
        """Resuelve el alias (flash/pro) al ID de modelo Gemini actual."""
        return self.GEMINI_MODELS.get(self.model, "gemini-2.0-flash")

    def test_key(self):
        if not self.api_key or len(self.api_key) < 10:
            return False, "API Key no configurada"
        try:
            import requests
        except ImportError:
            return False, "Falta el paquete 'requests' (pip install requests)"

        try:
            model_name = self._model_name()
            url = f"{self.base_url}/{model_name}:generateContent?key={self.api_key}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": "Hola"}]}]}, timeout=15)

            if r.status_code == 200:
                return True, "API Key válida"

            # Extraer el mensaje real del error del cuerpo JSON de Gemini
            detail, status = "", ""
            try:
                err = r.json().get("error", {})
                detail = (err.get("message") or "").strip()
                status = (err.get("status") or "").strip()
            except Exception:
                pass

            # Casos estructurados primero: la heuristica de texto solo como fallback
            if status == "PERMISSION_DENIED" or r.status_code == 403:
                return False, "Permiso denegado: habilita la Gemini API o revisa la facturación"
            if r.status_code == 401:
                return False, "Sin autenticación (401): revisa que la API Key sea válida"
            if r.status_code == 404:
                return False, f"Modelo no encontrado: {model_name}"
            if r.status_code == 429:
                return False, "Límite de cuota superado (429). Espera o revisa tu plan."
            if r.status_code >= 500:
                return False, "Error del servidor de Gemini. Intenta más tarde."

            low = (detail + " " + status).lower()
            if "api key" in low or "apikey" in low or "invalid" in low:
                return False, "API Key inválida (cópiala completa desde aistudio.google.com/app/apikey)"

            msg = detail or f"Error HTTP {r.status_code}"
            return False, f"{msg} (HTTP {r.status_code})"
        except requests.exceptions.Timeout:
            return False, "Tiempo de espera agotado. Revisa tu conexión a internet."
        except requests.exceptions.ConnectionError:
            return False, "No se pudo conectar con Gemini. Revisa tu conexión a internet."
        except Exception as e:
            return False, f"Error inesperado: {e}"

    def adapt(self, text, template_name, progress_callback=None):
        """Adapta texto usando Gemini. Segmenta automáticamente si es muy largo."""
        import requests

        if template_name not in self.TEMPLATES:
            return {"error": f"Template '{template_name}' no existe"}

        template = self.TEMPLATES[template_name]
        model_name = self._model_name()
        url = f"{self.base_url}/{model_name}:generateContent?key={self.api_key}"

        # Segmentación inteligente: si el texto es muy largo, usar enfoque map-reduce
        # Para Análisis Académico Profundo, usamos un umbral más bajo por la complejidad del prompt
        MAX_CHARS = 12000 if template_name == "Análisis Académico Profundo" else 15000

        if len(text) > MAX_CHARS:
            if progress_callback:
                progress_callback(1, 3, "Texto largo detectado. Segmentando para análisis profundo...")

            chunks = [text[i:i+MAX_CHARS] for i in range(0, len(text), MAX_CHARS)]
            partial_results = []

            for i, chunk in enumerate(chunks):
                if progress_callback:
                    progress_callback(1, 3, f"Analizando parte {i+1}/{len(chunks)}...")

                # Para análisis académico, usamos un prompt reducido por chunk
                if template_name == "Análisis Académico Profundo":
                    chunk_prompt = (
                        "Eres un filtro cognitivo académico. Analiza este FRAGMENTO de una clase "
                        "y extrae: 1) Ideas principales del orador, 2) Datos duros exactos, 3) "
                        "Tesis si es evidente. Ignora murmullos e interrupciones. NO inventes nada.\n\n"
                        f"FRAGMENTO {i+1}/{len(chunks)}:\n{chunk}\n\nEXTRACCIÓN:"
                    )
                else:
                    chunk_prompt = template["prompt"].replace("{TEXT}", chunk)

                payload = {
                    "contents": [{"parts": [{"text": chunk_prompt}]}],
                    "generationConfig": {
                        "temperature": template.get("temperature", 0.3),
                        "maxOutputTokens": 2048,
                        "topP": 0.9
                    }
                }

                try:
                    r = requests.post(url, json=payload, timeout=60)
                    if r.status_code == 200:
                        data = r.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            partial_results.append(candidates[0]["content"]["parts"][0]["text"])
                except Exception as e:
                    return {"error": f"Error en chunk {i+1}: {e}"}

            # Reduce: combinar resultados parciales con el prompt completo
            if progress_callback:
                progress_callback(2, 3, "Sintetizando análisis final...")

            combined = "\n\n".join(partial_results)

            if template_name == "Análisis Académico Profundo":
                final_prompt = (
                    self.ACADEMIC_PROMPT + "\n\n"
                    "A continuación recibirás EXTRACCIONES PARCIALES de una clase larga. "
                    "Tu tarea es sintetizarlas en UN SOLO análisis académico completo, "
                    "siguiendo estrictamente el formato de salida original (resumen ejecutivo, "
                    "tesis central, pilares argumentales, evidencia y datos duros, implicación, "
                    "y registro de filtrado). NO repitas información. Consolidad ideas similares.\n\n"
                    f"EXTRACCIONES PARCIALES:\n{combined}\n\n"
                    "ANÁLISIS ACADÉMICO FINAL:"
                )
            else:
                final_prompt = template["prompt"].replace("{TEXT}", combined)

            payload = {
                "contents": [{"parts": [{"text": final_prompt}]}],
                "generationConfig": {
                    "temperature": template.get("temperature", 0.2),
                    "maxOutputTokens": template.get("max_tokens", 4096),
                    "topP": 0.9
                }
            }
        else:
            # Texto corto: proceso directo con prompt completo
            prompt = template["prompt"].replace("{TEXT}", text)
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": template.get("temperature", 0.3),
                    "maxOutputTokens": template.get("max_tokens", 4096),
                    "topP": 0.9
                }
            }

        if progress_callback:
            progress_callback(2, 3, "Generando con Gemini...")

        try:
            r = requests.post(url, json=payload, timeout=120)
            if r.status_code != 200:
                return {"error": f"Gemini HTTP {r.status_code}: {r.text[:300]}"}

            data = r.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return {"error": "Gemini no generó respuesta"}

            result_text = candidates[0]["content"]["parts"][0]["text"]

            if progress_callback:
                progress_callback(3, 3, "¡Listo!")

            return {
                "text": result_text,
                "template": template_name,
                "model": model_name,
                "icon": template["icon"]
            }

        except Exception as e:
            return {"error": f"Error Gemini: {e}"}


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTACIÓN A GOOGLE DOCS (OAUTH 2.0)
# ═══════════════════════════════════════════════════════════════════════════════

class GoogleDocsExporter:
    """Exporta transcripciones y adaptaciones a Google Docs usando OAuth 2.0.

    Requiere:
      1. Un proyecto en Google Cloud Console con la Docs API habilitada
      2. Credenciales OAuth tipo "App de escritorio" (client_secret.json)
      3. google-auth-oauthlib + google-api-python-client instalados

    El token autorizado se guarda en ~/AudioClass_Recordings/google_token.json
    y se reutiliza/renueva automáticamente.
    """

    SCOPES = ["https://www.googleapis.com/auth/documents"]
    TOKEN_NAME = "google_token.json"

    def __init__(self, creds_path="", token_path=""):
        self.creds_path = creds_path
        self.token_path = token_path or os.path.join(OUTPUT_DIR, self.TOKEN_NAME)
        self.error = None

    def is_configured(self):
        return bool(self.creds_path) and os.path.exists(self.creds_path)

    def _load_creds(self, refresh=True):
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
        except ImportError:
            self.error = "Faltan librerías: pip install google-auth-oauthlib google-api-python-client"
            return None

        creds = None
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
            except Exception:
                creds = None

        if creds and creds.valid:
            return creds
        if refresh and creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                return creds
            except Exception:
                pass
        return None

    def _save_token(self, creds):
        try:
            with open(self.token_path, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception:
            pass

    def test_connection(self, refresh=False):
        """Comprueba si hay token válido (sin abrir navegador).
        refresh=False evita llamadas de red (para uso en el hilo principal)."""
        creds = self._load_creds(refresh=refresh)
        if creds:
            return True, "Conectado a Google"
        if self.is_configured():
            return False, "Sin autorizar (pulsa Conectar con Google)"
        return False, "Sin credenciales configuradas"

    def connect(self, progress_callback=None):
        """Flujo OAuth completo: abre el navegador, guarda el token. Bloqueante."""
        if not self.is_configured():
            self.error = "Selecciona primero tu archivo client_secret.json"
            return False

        creds = self._load_creds()
        if creds:
            return True

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError:
            self.error = "Faltan librerías: pip install google-auth-oauthlib google-api-python-client"
            return False

        if progress_callback:
            progress_callback(1, 2, "Abriendo el navegador para autorizar...")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(self.creds_path, self.SCOPES)
            creds = flow.run_local_server(port=0)
            self._save_token(creds)
            if progress_callback:
                progress_callback(2, 2, "Autorizado")
            return True
        except Exception as e:
            self.error = f"Error OAuth: {e}"
            return False

    def export(self, title, text, progress_callback=None):
        """Crea un documento nuevo en Google Docs con el texto. Devuelve dict."""
        creds = self._load_creds(refresh=True)
        if not creds:
            return {"error": "No conectado a Google. Conecta primero en Configuracion."}
        try:
            from googleapiclient.discovery import build
        except ImportError:
            return {"error": "Faltan librerías: pip install google-api-python-client"}

        if progress_callback:
            progress_callback(1, 2, "Creando documento en Google Docs...")
        try:
            service = build("docs", "v1", credentials=creds)
            doc = service.documents().create(body={"title": title}).execute()
            doc_id = doc["documentId"]

            # Insertar el texto en chunks (límite ~1MB por request; usamos 100k chars)
            CHUNK = 100000
            requests_list = []
            idx = 1
            for i in range(0, len(text), CHUNK):
                chunk = text[i:i+CHUNK]
                requests_list.append({"insertText": {"location": {"index": idx}, "text": chunk}})
                idx += len(chunk)

            if requests_list:
                service.documents().batchUpdate(documentId=doc_id, body={"requests": requests_list}).execute()

            if progress_callback:
                progress_callback(2, 2, "¡Listo!")
            return {"url": f"https://docs.google.com/document/d/{doc_id}/edit", "doc_id": doc_id, "title": title}
        except Exception as e:
            return {"error": f"Error al exportar: {e}"}


# ═══════════════════════════════════════════════════════════════════════════════
# UI PRINCIPAL — AudioClass v9.1 (continuación)
# ═══════════════════════════════════════════════════════════════════════════════

# Simbolos tipograficos comunes -> sustituto ASCII. Solo se aplican como
# compatibilidad cuando NO hay fuente Unicode (con DejaVu no hacen falta).
_PDF_FALLBACK_CHARS = {
    "—": "-", "–": "-", "…": "...", "•": "-", "→": "->",
    "├": "|", "└": "`", "“": '"', "”": '"', "‘": "'", "’": "'",
}

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

            if self.config.get("first_run", True):
                # Asistente de bienvenida: ventana compacta que quepa en
                # portatiles (la principal se restaura al terminar).
                self.geometry("1120x720")
                self.minsize(900, 560)
            else:
                self.geometry("1450x1050")
                self.minsize(1250, 900)

            self.recording = False
            self.buffer = []
            self.vizbuf = np.zeros(VISUAL_SAMPLES, dtype=np.float32)
            self.last_path = None
            self.last_text = ""
            self.last_segments = []
            self.cancel = False
            self.stop_ev = threading.Event()
            self.q = queue.Queue()
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

            self.local_engine = LocalWhisperEngine(self.config.get("local_model", "tiny"))
            self.cloud_engine = CloudColabEngine(
                self.config.get("colab_url", ""),
                self.config.get("colab_key", "audioclass")
            )
            self.gemini_engine = GeminiAdaptationEngine(
                self.config.get("gemini_api_key", ""),
                self.config.get("gemini_model", "flash")
            )
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
        if CTK:
            w = ctk.CTkButton(p, text=txt, command=cmd, **d)
            # Registrar los botones con color de paleta para re-tematizarlos en
            # el cambio claro/oscuro (igual que _lbl/_frame). Los que usan
            # colores fijos (hover literales, estado dinamico) no se registran.
            if not no_theme:
                fg = d.get("fg_color")
                if fg and fg != "transparent":
                    key = self._palette_key(fg)
                    if key:
                        self._themeable.append(("frame", w, key))
            return w
        b = ctk.Button(p, text=txt, command=cmd, font=d.get("font"))
        if "state" in d: b.config(state=d["state"])
        if "fg_color" in d: b.config(bg=d["fg_color"], fg="white")
        return b

    def _lbl(self, p, txt, **kw):
        if CTK:
            w = ctk.CTkLabel(p, text=txt, **kw)
            col = kw.get("text_color", C["text"])
            if col:
                key = self._palette_key(col)
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
        self._lbl(f2, "3. ¿Tienes la API Key de Gemini? (opcional, pero recomendada)",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        self._lbl(f2, "Sirve para analizar tus clases con IA (resúmenes, guías, exámenes). Es gratis: aistudio.google.com/app/apikey",
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
            ctk.CTkRadioButton(f3, text="☁️ En Google Colab (máxima precisión, necesita internet)", 
                               variable=self.wiz_mode, value="cloud",
                               font=("Segoe UI", 12), fg_color=C["accent"]).pack(anchor="w", padx=30, pady=5)
        else:
            ctk.Radiobutton(f3, text="En mi computadora", variable=self.wiz_mode, value="local",
                           bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)
            ctk.Radiobutton(f3, text="En Google Colab", variable=self.wiz_mode, value="cloud",
                           bg=C["card"], fg=C["text"], selectcolor=C["accent"]).pack(anchor="w", padx=30, pady=5)

        # (El boton "Comenzar" y la nota estan en la barra fija inferior)

    def _finish_wizard(self):
        # Guarda contra doble disparo (Enter rapido + clic en el boton): la
        # segunda llamada encontraria los widgets del asistente destruidos.
        if getattr(self, "_wiz_finishing", False):
            return
        self._wiz_finishing = True
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
        self.gemini_engine = GeminiAdaptationEngine(gemini_key, self.config.get("gemini_model", "flash"))

        self.wizard.destroy()
        self._build_main_ui()
        # Restaurar el tamano de ventana de la app completa
        try:
            self.geometry("1450x1050")
            self.minsize(1250, 900)
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
        sb.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(15, 8), pady=15)
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
        self.bdel = self._btn(bf, "Eliminar", self._delh, state="disabled", width=260, height=32, fg_color=C["err"], hover_color="#dc2626")
        self.bdel.pack(fill="x", pady=(0, 6))
        self.bcompile = self._btn(bf, "Compilar Todo", self._compile, state="disabled", width=260, height=32, fg_color=C["cloud"], hover_color="#7c3aed")
        self.bcompile.pack(fill="x", pady=(0, 6))
        self.bguide = self._btn(bf, "❓ Guía Rápida", self._open_guide, width=260, height=32, fg_color=C["accent"], hover_color=C["accent_hover"])
        self.bguide.pack(fill="x", pady=(0, 6))
        self.bconfig = self._btn(bf, "⚙️ Configuración", self._open_config, width=260, height=32)
        self.bconfig.pack(fill="x", pady=(0, 6))
        self.badv = self._btn(bf, "⚙️ Opciones avanzadas", self._toggle_advanced, width=260, height=32,
                              fg_color=C["cloud"], hover_color="#7c3aed")
        self.badv.pack(fill="x")

        mn = self._frame(self, fg_color=C["bg"])
        mn.grid(row=0, column=1, sticky="nsew", padx=(8, 15), pady=15)
        mn.grid_columnconfigure(0, weight=1)
        mn.grid_rowconfigure(6, weight=1)

        hd = self._frame(mn, fg_color=C["header"], border_width=1, border_color=C["border"], theme_key="header")
        hd.grid(row=0, column=0, sticky="ew", padx=22, pady=(14, 8))
        hd.grid_columnconfigure(0, weight=1)
        brand = self._frame(hd, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(18, 8), pady=(8, 2))
        self._lbl(brand, "🎓", font=(self.FH, 24)).pack(side="left", padx=(0, 12))
        btb = self._frame(brand, fg_color="transparent")
        btb.pack(side="left")
        self._lbl(btb, APP_NAME, font=(self.FH, 21, "bold"), text_color="#FFFFFF").pack(anchor="w")
        self._lbl(btb, "Grabación y transcripción académica con IA",
                  font=(self.FB, 11), text_color=C["muted"]).pack(anchor="w")
        hdr = self._frame(hd, fg_color="transparent")
        hdr.grid(row=0, column=1, sticky="e", padx=(8, 16), pady=(8, 2))
        self.lconn = self._lbl(hdr, "🖥️ Motor local", font=(self.FB, 11), text_color=C["muted"])
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
        steps.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(10, 0))
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
        self._lbl(hd, "👆 Pulsa un paso para ver cómo se hace",
                  font=(self.FB, 10), text_color=C["muted"]).grid(row=3, column=0, columnspan=2, sticky="w", padx=18, pady=(4, 0))
        self._set_step(1)

        # Banner permanente "Siguiente paso": tras el asistente y durante todo
        # el flujo, el usuario siempre sabe QUE hacer a continuacion. Se
        # actualiza solo con _update_next_step() segun el estado (grabar,
        # transcribir, analizar o guardar) y el boton de ayuda abre la Guia
        # Rapida en la seccion de ese paso.
        nx = self._frame(hd, fg_color=C["card"], border_width=2, border_color=C["accent"])
        nx.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 2))
        nx.grid_columnconfigure(0, weight=1)
        self.next_step_frame = nx
        self.lnext = self._lbl(nx, "", font=(self.FH, 15, "bold"), text_color=C["accent"],
                               anchor="w", wraplength=1000)
        self.lnext.grid(row=0, column=0, sticky="ew", padx=(16, 8), pady=(10, 2))
        self.lnext_sub = self._lbl(nx, "", font=(self.FB, 11), text_color=C["muted"],
                                   anchor="w", wraplength=1000)
        self.lnext_sub.grid(row=1, column=0, sticky="ew", padx=(16, 8), pady=(0, 4))
        self._btn(nx, "❓ ¿Cómo se hace?", lambda: self._open_guide(self._next_guide_step or 1),
                  width=170, height=32, font=(self.FB, 11), fg_color=C["accent"],
                  hover_color=C["accent_hover"]).grid(row=0, column=1, rowspan=2, padx=(8, 16), pady=8)

        easy = self._frame(mn, fg_color=C["card"], border_width=2, border_color=C["easy"])
        easy.grid(row=1, column=0, sticky="ew", padx=22, pady=10)

        self._lbl(easy, "MODO FACIL", font=(self.FH, 16, "bold"), text_color=C["easy"]).pack(anchor="w", padx=18, pady=(12, 4))
        self._lbl(easy, "Un solo boton hace TODO: Grabar → Procesar → Transcribir → Analizar Academicamente",
                   font=(self.FB, 11), text_color=C["muted"]).pack(anchor="w", padx=18, pady=(0, 8))

        easy_row = self._frame(easy, fg_color="transparent")
        easy_row.pack(fill="x", padx=18, pady=(0, 12))

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
                               font=(self.FB, 26), fg_color=C["accent"], hover_color=C["accent_hover"],
                               no_theme=True)
        self.brec.pack(side="left", padx=(18, 12), pady=14)

        self.bstop = self._btn(ct, "🛑 Detener", self._stoprec, width=150, height=52,
                                font=(self.FB, 14, "bold"), fg_color=C["err"], hover_color="#DC2626")
        self.bstop.pack(side="left", padx=(0, 12), pady=16)
        self.bstop.pack_forget()

        self.btr = self._btn(ct, "📝 Transcribir", lambda: self._starttrans(False), width=150, height=42, state="disabled")
        self.btr.pack(side="left", padx=(0, 8), pady=16)
        self.bts = self._btn(ct, "⏱️ Con tiempos", lambda: self._starttrans(True), width=130, height=42, state="disabled")
        self.bts.pack(side="left", padx=(0, 8), pady=16)
        self.bpdf = self._btn(ct, "📄 Guardar PDF", self._pdf, width=130, height=42, state="disabled")
        self.bpdf.pack(side="left", padx=(0, 8), pady=16)
        self.bdocs = self._btn(ct, "🌐 Google Docs", self._export_docs, width=140, height=42, state="disabled",
                                fg_color=C["ok"], hover_color="#059669")
        self.bdocs.pack(side="left", padx=(0, 8), pady=16)
        self.bcancel = self._btn(ct, "Cancelar", self._cancel, width=100, height=42, state="disabled",
                                  fg_color=C["err"], hover_color="#dc2626")
        self.bcancel.pack(side="left", padx=(0, 18), pady=16)

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
        self.lstatus.pack(side="right", padx=(20, 18), pady=16)

        cfg = self._frame(mn, fg_color=C["card"])
        cfg.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))
        self.cfg_frame = cfg

        # Resumen de la configuracion activa: ocupa la misma fila que los
        # controles (Perfil/Motor/Modelo) y se muestra cuando el Modo Guiado
        # los oculta, para que el usuario sepa que hay sin ver los controles.
        cfg_sum = self._frame(mn, fg_color=C["card"])
        cfg_sum.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 10))
        self.cfg_sum_frame = cfg_sum
        self.lcfg_sum = self._lbl(cfg_sum, "", font=("Segoe UI", 11), text_color=C["muted"])
        self.lcfg_sum.pack(anchor="w", padx=18, pady=12)

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
            ctk.CTkSegmentedButton(cfg, values=["local", "cloud"], variable=self.mode_var,
                                   font=("Segoe UI", 11), command=self._chmode).pack(side="left", padx=(0, 20), pady=12)
        else:
            ctk.OptionMenu(cfg, self.mode_var, "local", "cloud", command=self._chmode).pack(side="left", padx=(0, 20), pady=12)

        self._lbl(cfg, "Modelo:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 6), pady=12)
        self.model_var = ctk.StringVar(value=self.config.get("local_model", "tiny"))
        if CTK:
            self.cmb_model = ctk.CTkOptionMenu(cfg, values=["tiny", "base", "small"], 
                                                variable=self.model_var, width=90,
                                                command=self._chlocalmodel, font=("Segoe UI", 11))
        else:
            self.cmb_model = ctk.OptionMenu(cfg, self.model_var, "tiny", "base", "small", command=self._chlocalmodel)
        self.cmb_model.pack(side="left", padx=(0, 20), pady=12)

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
        vz.grid(row=5, column=0, sticky="nsew", padx=22, pady=(0, 10))

        if MPL:
            self.fig = Figure(figsize=(8, 2.2), dpi=100, facecolor=C["card"])
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
            self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        else:
            self._lbl(vz, "Instala matplotlib: pip install matplotlib", text_color=C["warn"]).pack(pady=35)

        adapt = self._frame(mn, fg_color=C["card"], border_width=1, border_color=C["gemini"])
        adapt.grid(row=6, column=0, sticky="nsew", padx=22, pady=(0, 18))
        adapt.grid_rowconfigure(2, weight=1)
        adapt.grid_columnconfigure(0, weight=1)

        ah = self._frame(adapt, fg_color="transparent")
        ah.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        self._lbl(ah, "Adaptacion Inteligente (Gemini)", font=("Segoe UI", 14, "bold"), text_color=C["gemini"]).pack(side="left")
        self.lgemini = self._lbl(ah, "Sin API Key", font=("Segoe UI", 11), text_color=C["warn"])
        self.lgemini.pack(side="right")

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
                                             fg_color=C["bg"], text_color=C["text"], height=220)
        else:
            self.adapt_txt = scrolledtext.ScrolledText(adapt, wrap=ctk.WORD, font=("Consolas", 11), 
                                                        bg=C["bg"], fg=C["text"], height=11)
        self.adapt_txt.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 14))
        self.adapt_txt.configure(state="disabled")

        self.bsave_adapt = self._btn(adapt, "Guardar Adaptacion", self._save_adaptation,
                                      width=180, height=36, state="disabled")
        self.bsave_adapt.grid(row=5, column=0, sticky="w", padx=18, pady=(0, 12))

        tr = self._frame(mn, fg_color=C["card"], border_width=1, border_color=C["border"])
        tr.grid(row=7, column=0, sticky="nsew", padx=22, pady=(0, 14))
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
        self.txt_gutter = tk.Text(tbox, width=4, wrap="none", state="disabled",
                                  bg=C["card"], fg=C["muted"], font=(self.FM, 11),
                                  padx=6, pady=8, relief="flat", borderwidth=0,
                                  highlightthickness=0, takefocus=0)
        self.txt_gutter.grid(row=0, column=0, sticky="nsew")

        # Area de transcripcion: tk.Text (permite tags + gutter) estilo codigo
        self.txt = tk.Text(tbox, wrap="word", state="disabled",
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
        ft.grid(row=8, column=0, sticky="ew", padx=22, pady=(0, 12))
        ftl = self._frame(ft, fg_color="transparent")
        ftl.pack(side="left")
        self._lbl(ftl, f"📁 {OUTPUT_DIR}", font=(self.FB, 10), text_color=C["muted"]).pack(side="left")
        self._lbl(ft, "Espacio ▶  ·  Ctrl+R grabar  ·  Ctrl+S guardar  ·  Ctrl+E exportar  ·  F1 ayuda",
                  font=(self.FB, 10), text_color=C["muted"]).pack(side="right", padx=(0, 18))
        self._btn(ftl, "📂 Abrir carpeta", self._open_output_dir, width=130, height=28,
                  font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))
        self._btn(ftl, "🎤 Probar micrófono", self._test_mic, width=170, height=28,
                  font=("Segoe UI", 10), fg_color=C["accent"], hover_color=C["accent_hover"]).pack(side="left", padx=(8, 0))
        self.ltime = self._lbl(ft, "", font=("Segoe UI", 10), text_color=C["muted"])
        self.ltime.pack(side="right")

        self._loadhist()
        self._update_gemini_status()
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
            modelo = self.config.get("local_model", "tiny")
        txt = f"Usando perfil: {perfil} · motor: {modo} · modelo: {modelo}"
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
        if mode == "local":
            self.cmb_model.configure(state="normal")
            self.lmodel.configure(text=f"Local: {self.model_var.get()}", text_color=C["muted"])
            if hasattr(self, "lconn"):
                self.lconn.configure(text=f"🖥️ Motor local · {self.model_var.get()}", text_color=C["muted"])
        else:
            self.cmb_model.configure(state="disabled")
            if self.config.get("colab_url"):
                self.lmodel.configure(text="Cloud: Colab GPU", text_color=C["cloud"])
                if hasattr(self, "lconn"):
                    self.lconn.configure(text="☁️ Motor Cloud · GPU", text_color=C["cloud"])
            else:
                self.lmodel.configure(text="Cloud: Sin URL", text_color=C["warn"])
                if hasattr(self, "lconn"):
                    self.lconn.configure(text="☁️ Motor Cloud · sin URL", text_color=C["warn"])

    def _chlocalmodel(self, name):
        self.config["local_model"] = name
        save_config(self.config)
        self.local_engine = LocalWhisperEngine(name)
        self._update_cfg_summary()
        self.local_engine.load(callback=self._on_model_loaded)
        self.lmodel.configure(text=f"Cargando {name}...", text_color=C["warn"])

    def _on_model_loaded(self, status, msg):
        if status == "ready":
            self.q.put(("model_ready", msg))
        else:
            self.q.put(("model_err", msg))

    def _update_gemini_status(self):
        key = self.config.get("gemini_api_key", "")
        if key and len(key) > 10:
            self.lgemini.configure(text="Gemini listo", text_color=C["ok"])
        else:
            self.lgemini.configure(text="Sin API Key", text_color=C["warn"])

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
                        lbl.configure(text_color=C["bg"], fg_color=C["accent"])
                    elif step < n:
                        lbl.configure(text_color=C["ok"], fg_color=C["button"])
                    else:
                        lbl.configure(text_color=C["muted"], fg_color=C["button"])
                else:
                    lbl.configure(fg=(C["bg"] if step == n else (C["ok"] if step < n else C["muted"])),
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
                main = "🎓 Añade tu API Key de Gemini (es gratis)"
                sub = "Configuración → pega tu key de aistudio.google.com/app/apikey y podrás analizar."
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
            col = "#E8C96A" if self._pulse_on else C["accent"]
            try:
                self.brec.configure(fg_color=col, hover_color=C["accent_hover"])
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
                self.brec.configure(fg_color=C["accent"], hover_color=C["accent_hover"])
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

        _PILL = {
            "ok":   ("#065f46", "#a7f3d0"),   # verde oscuro / verde claro
            "err":  ("#7f1d1d", "#fecaca"),   # rojo oscuro / rojo claro
            "warn": ("#78350f", "#fde68a"),   # ambar oscuro / ambar claro
        }
        _PULSE = {"ok": "#6ee7b7", "err": "#fca5a5", "warn": "#fcd34d"}
        pill_bg, pill_fg = _PILL.get(kind, _PILL["ok"])
        pulse_col = _PULSE.get(kind, "#6ee7b7")
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
                  hover_color="#059669").pack(pady=(0, 18))

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

    def _test_gemini(self, entry, model_var):
        """Prueba la API Key de Gemini desde la ventana de configuracion (asincrono)."""
        try:
            # El dialogo pudo haberse cerrado (auto-test con after): no tocar widgets destruidos
            if not (hasattr(self, "gemini_test_lbl") and self.gemini_test_lbl.winfo_exists()):
                return
            key = entry.get().strip()
            model = model_var.get()  # leer en el hilo principal, nunca dentro del worker
        except Exception:
            return

        if len(key) < 10:
            self.gemini_test_lbl.configure(text="Introduce una API Key primero", text_color=C["warn"])
            return
        if hasattr(self, "btn_test_gemini") and self.btn_test_gemini.winfo_exists():
            self.btn_test_gemini.configure(state="disabled", text="Probando...")
        self.gemini_test_lbl.configure(text="Probando conexión con Gemini...", text_color=C["warn"])

        def worker():
            try:
                engine = GeminiAdaptationEngine(key, model)
                self.q.put(("gemini_test", engine.test_key()))
            except Exception as e:
                self.q.put(("gemini_test", (False, f"Error inesperado: {e}")))

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

        content = self.last_text
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
                                      width=280, height=44, font=("Segoe UI", 14, "bold"),
                                      fg_color=C["err"], hover_color="#dc2626")
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

    def _open_config(self):
        top = ctk.CTkToplevel(self) if CTK else ctk.Toplevel(self)
        top.title("Configuracion de AudioClass")
        top.geometry("650x920")
        top.transient(self)
        top.grab_set()

        f1 = self._frame(top, fg_color=C["card"])
        f1.pack(fill="x", padx=20, pady=10)
        self._lbl(f1, "API Key de Google AI Studio (Gemini)", font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        self._lbl(f1, "Consiguela gratis en: aistudio.google.com/app/apikey", font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 8))
        gemini_entry = self._entry(f1, width=500, font=("Segoe UI", 11))
        gemini_entry.pack(anchor="w", padx=15, pady=(0, 8))
        gemini_entry.insert(0, self.config.get("gemini_api_key", ""))

        gemini_model = ctk.StringVar(value=self.config.get("gemini_model", "flash"))
        if CTK:
            ctk.CTkSegmentedButton(f1, values=["flash", "pro"], variable=gemini_model,
                                   font=("Segoe UI", 11)).pack(anchor="w", padx=15, pady=(0, 12))
        else:
            ctk.OptionMenu(f1, gemini_model, "flash", "pro").pack(anchor="w", padx=15, pady=(0, 12))
        self._lbl(f1, "flash = rapido y economico (Gemini 2.0 Flash) | pro = maxima calidad (Gemini 2.5 Pro)", font=("Segoe UI", 10), text_color=C["muted"]).pack(anchor="w", padx=15, pady=(0, 12))

        test_row = self._frame(f1, fg_color="transparent")
        test_row.pack(fill="x", padx=15, pady=(0, 12))
        self.gemini_test_lbl = self._lbl(test_row, "", font=("Segoe UI", 10), text_color=C["muted"])
        self.gemini_test_lbl.pack(side="left", padx=(0, 10))
        self.btn_test_gemini = self._btn(test_row, "Probar Conexión",
                                         lambda: self._test_gemini(gemini_entry, gemini_model),
                                         width=150, height=30, fg_color=C["accent"])
        self.btn_test_gemini.pack(side="left")

        if self.config.get("gemini_api_key"):
            self.after(400, lambda: self._test_gemini(gemini_entry, gemini_model))

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
                  fg_color=C["err"], hover_color="#dc2626").pack(anchor="w", padx=15, pady=(0, 12))

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
        try:
            gok, gmsg = self.docs_exporter.test_connection(refresh=False)
            self.gdoc_lbl.configure(text=("✓ " if gok else "· ") + gmsg,
                                    text_color=C["ok"] if gok else C["muted"])
        except Exception:
            pass

        def save():
            self.config["gemini_api_key"] = gemini_entry.get().strip()
            self.config["gemini_model"] = gemini_model.get()
            self.config["colab_url"] = colab_entry.get().strip()
            self.config["colab_key"] = colab_key.get().strip()
            self.config["google_creds_path"] = gdoc_entry.get().strip()
            save_config(self.config)

            self.gemini_engine = GeminiAdaptationEngine(
                self.config["gemini_api_key"], self.config["gemini_model"]
            )
            self.cloud_engine = CloudColabEngine(
                self.config["colab_url"], self.config["colab_key"]
            )
            self.docs_exporter = GoogleDocsExporter(
                self.config["google_creds_path"]
            )
            self._update_gemini_status()
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
                               hover_color=C["border"], border_width=1, border_color=C["border"],
                               command=lambda p=path: self._selhist(p))
            b.pack(fill="x", pady=(0, 4), padx=2)
            b._path = path
        else:
            b = ctk.Button(self.hist_frame, text=name, anchor="w", font=("Segoe UI", 11),
                            bg=C["card"], fg=C["text"], command=lambda p=path: self._selhist(p))
            b.pack(fill="x", pady=(0, 4))
            b._path = path

    def _selhist(self, path):
        self.sel = path
        self.bplay.configure(state="normal")
        self.btransh.configure(state="normal")
        self.bdel.configure(state="normal")
        self.bcompile.configure(state="normal" if self.compile_buffer else "disabled")
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
        if not self._disk_ok(100):
            self._msg("warning", "Espacio", "Necesitas 100 MB libres.")
            return
        try:
            sd.check_input_settings(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE)
        except Exception as e:
            self._msg("error", "Microfono", str(e))
            return

        self.recording = True
        self.stop_ev.clear()
        self.buffer = []
        self._audio_overflows = 0
        self.vu_clips = 0
        self.vu_low = 0
        self.vu_rms_hist = []
        self.vu_static = False
        self.vu_rms_hist_full = []
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
        self.bstop.pack(side="left", padx=(18, 12), pady=16)
        self.lstatus.configure(text="● GRABANDO", text_color=C["err"])
        self.btr.configure(state="disabled")
        self.bts.configure(state="disabled")
        self.bpdf.configure(state="disabled")
        self.bdocs.configure(state="disabled")
        self._disable_adapt_buttons()
        self._cleartxt()
        self._clear_adapt()
        self._apptxt(f"Grabacion iniciada...\nPerfil: {self.pipeline.profile}\nManten silencio los primeros segundos para perfil de ruido.\n\n")

        self.t0rec = time.time()
        self._updtimer()
        threading.Thread(target=self._recloop, daemon=True).start()
        if MPL: self._updviz()
        self._updvu()

    def _stoprec(self):
        self.recording = False
        self.stop_ev.set()
        self.bstop.pack_forget()
        self.brec.pack(side="left", padx=(18, 12), pady=16)
        self.lstatus.configure(text="Procesando audio profesional...", text_color=C["warn"])
        self.ltime.configure(text="")
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

        if not self.buffer:
            self.lstatus.configure(text="No se capturo audio", text_color=C["warn"])
            return
        threading.Thread(target=self._procsave, daemon=True).start()

    def _recloop(self):
        # El callback de audio debe ser lo mas ligero posible: si tarda mas que
        # la duracion de un bloque, PortAudio pierde muestras y la grabacion
        # sale con estatica y cortes. Solo se copia el bloque a la lista; el
        # buffer visual se reconstruye en el hilo principal (_updviz).
        def cb(indata, frames, ti, status):
            if status and status.input_overflow:
                self._audio_overflows += 1
            if self.recording:
                self.buffer.append(indata.copy())
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
                                blocksize=CHUNK_SIZE, callback=cb):
                self.stop_ev.wait()
        except Exception as e:
            self.q.put(("status", f"Error: {str(e)[:40]}"))
            self.recording = False

    def _updtimer(self):
        if self.recording:
            m, s = divmod(int(time.time() - self.t0rec), 60)
            self.ltime.configure(text=f"{m:02d}:{s:02d}")
            # Indicador REC parpadeante mientras se graba
            dot = "●" if int(time.time() * 2) % 2 == 0 else "○"
            self.lstatus.configure(text=f"{dot} GRABANDO", text_color=C["err"])
            self.after(500, self._updtimer)

    def _updviz(self):
        if self.recording and MPL:
            if self.buffer:
                # Solo se usan las ultimas muestras; concatenar todo el buffer
                # cada fotograma seria O(n) en clases largas.
                need = int(np.ceil(VISUAL_SAMPLES / CHUNK_SIZE)) + 2
                recent = np.concatenate(self.buffer[-need:])
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
        try:
            raw = np.concatenate(self.buffer).flatten()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

            rp = os.path.join(OUTPUT_DIR, f"clase_{ts}_raw.wav")
            self._savewav(rp, raw)
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
            self.q.put(("status", f"Error: {str(e)[:50]}"))
            self.q.put(("log", f"Error: {e}\n"))

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

            result = self.local_engine.transcribe(path, timestamps, 
                                                   cancel_event=self.stop_ev,
                                                   progress_callback=progress)

            if result.get("cancelled"):
                self.q.put(("log", "\nCancelado.\n"))
                self.q.put(("status", "Cancelado"))
                self.q.put(("enable", None))
                return

            if "error" in result:
                raise Exception(result["error"])

            self._process_transcription_result(result, path, timestamps, auto_adapt)

        except Exception as e:
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

        self.q.put(("trans_done", text))
        self.q.put(("log", f"\nTranscripcion completada\n{result.get('model','?')} | {result.get('device','?')}\nGuardado\n"))
        self.q.put(("status", "Transcripcion lista"))
        self.q.put(("enable", None))

        self.compile_buffer.append({"text": text, "path": path, "ts": datetime.now().isoformat()})

        if auto_adapt or self.config.get("auto_adaptar", False):
            template = self.easy_template.get()
            self.after(500, lambda: self._adapt(template))

    def _adapt(self, template_name):
        if not self.last_text:
            self._msg("warning", "Sin transcripcion", "Primero transcribe un audio.")
            return

        key = self.config.get("gemini_api_key", "")
        if not key or len(key) < 10:
            self._msg("warning", "Sin API Key", "Configura tu API Key de Gemini en Configuracion (aistudio.google.com/app/apikey)")
            return

        info = GeminiAdaptationEngine.TEMPLATES.get(template_name, {})
        self.adapt_info.configure(text=f"{info.get('icon','')} {info.get('desc','')}")

        self._disable_adapt_buttons()
        self.bcancel.configure(state="normal")
        self.lstatus.configure(text=f"Adaptando: {template_name}...", text_color=C["gemini"])
        self._apptxt(f"\nIniciando adaptacion: {template_name}...\n")

        threading.Thread(target=self._adapt_worker, args=(self.last_text, template_name), daemon=True).start()

    def _adapt_worker(self, text, template_name):
        try:
            def progress(current, total, msg):
                self.q.put(("progress", (current / total, msg)))

            result = self.gemini_engine.adapt(text, template_name, progress_callback=progress)

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
                f.write(f"Motor: Gemini {result.get('model', '?')}\n")
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
        self.adapt_txt.insert("end", f"{icon} {title}\n{'='*55}\n\n{text}\n")
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
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font(fam, tit_style, 16)
            pdf.cell(0, 10, "Transcripcion de Clase", ln=True, align="C")
            pdf.ln(5)
            pdf.set_font(fam, "", 10)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 6, f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
            pdf.cell(0, 6, "Modelo: Whisper", ln=True)
            pdf.ln(8)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(8)
            pdf.set_font(fam, "", 11)
            pdf.set_text_color(30, 30, 30)
            t = self.last_text if full_unicode else self._pdf_fallback_text(self.last_text)
            pdf.multi_cell(0, 7, t)
            pdf.output(fp)
            self._set_step(4)
            self._msg("info", "PDF Exportado", f"Guardado en:\n{fp}")
            self.q.put(("log", "PDF exportado\n"))
        except Exception as e:
            self._msg("error", "Error PDF", str(e))

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
        """Muestra en vivo el tiempo transcurrido mientras se transcribe, para
        que el usuario sepa que el proceso avanza (Whisper local tarda mucho
        por chunk y sin esto parece congelado en 'Iniciando transcripcion')."""
        if not self._transcribing:
            return
        try:
            el = int(time.time() - self._trans_start)
            m, s = divmod(el, 60)
            msg = self._trans_msg or "Transcribiendo..."
            self.lprog.configure(text=f"{msg}  ·  {m:02d}:{s:02d}")
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
                    self._clear_live()
                    self.btr.configure(state="normal")
                    self.bts.configure(state="normal")
                    self.bpdf.configure(state="normal")
                    self.bdocs.configure(state="normal")
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

                elif mt == "gemini_test":
                    ok, msg = d
                    try:
                        if hasattr(self, "gemini_test_lbl") and self.gemini_test_lbl.winfo_exists():
                            self.gemini_test_lbl.configure(
                                text=("✓ " if ok else "✗ ") + msg,
                                text_color=C["ok"] if ok else C["err"])
                        if hasattr(self, "btn_test_gemini") and self.btn_test_gemini.winfo_exists():
                            self.btn_test_gemini.configure(state="normal", text="Probar Conexión")
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
                            self.bdocs.configure(state="normal", text="🌐 Google Docs")
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
                    if CTK: self.pbar.set(p)
                    else: self.pbar['value'] = p * 100
                    self.lprog.configure(text=l)

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
        if self.recording:
            self.recording = False
            self.stop_ev.set()
        self.cancel = True
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
            eng = LocalWhisperEngine("tiny")
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
