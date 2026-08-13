#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AudioClass v9.1 — NUCLEO DE PROCESAMIENTO (separado de la UI, mejora #9)
=======================================================================
Logica pura sin interfaz: pipeline de audio profesional, motores de
transcripcion (local Whisper paralelo / Cloud Colab), adaptacion inteligente
con Gemini y exportacion a Google Docs. audioclass_v91.py importa estas clases
para mantener el archivo de la interfaz enfocado en la UI.
"""
import os, sys, threading, time, copy, warnings, logging, base64, json
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

warnings.filterwarnings("ignore")


def _free_ram_mb():
    """RAM libre en MB usando SOLO la stdlib (None si no se puede medir).
    Windows: GlobalMemoryStatusEx; Linux: /proc/meminfo. No agrega dependencias
    al bundle y permite escalar los workers de transcripcion con la RAM real."""
    try:
        if os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
                return int(ms.ullAvailPhys // (1024 * 1024))
        elif os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
    except Exception:
        pass
    return None


# ─── CONSTANTES DE AUDIO (fuente unica; v91 tambien las define identicas) ────
APP_NAME = "AudioClass"
APP_VER = "9.1 Académica"
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.float32
CHUNK_DUR = 0.1   # 100 ms por bloque: reduce desbordamientos (estatica/cortes)
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DUR)
VISUAL_SAMPLES = int(SAMPLE_RATE * 2.0)
# Presupuesto global de la cache de modelos Whisper (deepcopies entre corridas):
# 6 copias = ~450 MB con tiny, ~850 MB con base, ~2.8 GB con small como tope
# absoluto por proceso, independientemente de cuantas rutas de modelo se usen.
_MODEL_CACHE_MAX = 6

# Presupuesto de TIEMPO por chunk de transcripcion (s). Si whisper se cuelga
# (bucle de timestamps sin avanzar en la misma ventana de 30s), el chunk se
# OMITE en vez de esperar horas: max(piso, 4x la media real por chunk). El piso
# cubre maquinas lentas (tiny/base terminan un chunk de 30s en < 60s). Los
# tests lo bajan para verificar el watchdog sin esperar 2 minutos.
CHUNK_BUDGET_FLOOR = 120.0
CHUNK_EST_SEED = 30.0   # estimacion inicial de segundos por chunk (1x 30s)

OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "AudioClass_Recordings")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── LOGGING ROTATIVO ────────────────────────────────────────────────────────
LOG_DIR = os.path.join(OUTPUT_DIR, "logs")
_logger = None
def _setup_logger():
    global _logger
    if _logger is not None:
        return _logger
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        fh = RotatingFileHandler(os.path.join(LOG_DIR, "audioclass.log"),
                                 maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(threadName)s] %(message)s"))
        _logger = logging.getLogger("audioclass")
        _logger.setLevel(logging.INFO)
        _logger.addHandler(fh)
        _logger.propagate = False
    except Exception:
        _logger = logging.getLogger("audioclass")
        _logger.addHandler(logging.NullHandler())
    return _logger

def log_exc(msg="Error no controlado"):
    """Registra la excepcion actual (desde except) con su traceback."""
    try:
        _setup_logger().exception(msg)
    except Exception:
        pass

def log_info(msg):
    try:
        _setup_logger().info(msg)
    except Exception:
        pass

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
        # Umbral de duracion (s): archivos mas largos usan un pipeline rapido
        # (noisereduce estacionario con n_fft menor) para no tardar mas que la
        # transcripcion misma en clases de 1h+.
        self.long_audio_sec = 1200.0

    def process(self, audio, progress_callback=None):
        audio = audio.astype(np.float64)
        steps = 9 if not self.fast_mode else 5
        step = 0
        long_audio = len(audio) / SAMPLE_RATE > self.long_audio_sec

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
                if long_audio:
                    # Archivo largo: ruido estacionario + n_fft 512 (mucho mas
                    # rapido) en vez de no-estacionario con n_fft 1024. La
                    # perdida de calidad es minima y evita que el pipeline
                    # tarde mas que la transcripcion en clases de 1h+.
                    audio = nr.reduce_noise(
                        y=audio, y_noise=npf, sr=SAMPLE_RATE,
                        prop_decrease=min(self.p["noise_decrease"], 0.6),
                        stationary=True, n_fft=512, n_jobs=2
                    )
                    report("Reducción de ruido (modo archivo largo)")
                else:
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


def audio_silence_stats(data, sample_rate=SAMPLE_RATE):
    """Metricas de silencio digital de un array float32 [-1, 1]. Devuelve un
    dict con zero_frac (fraccion de muestras EXACTAMENTE cero, sello de un
    microfono muerto/desenchufado), rms global y pico. No lanza excepciones."""
    if data is None or len(data) == 0:
        return {"zero_frac": 1.0, "rms": 0.0, "peak": 0.0, "samples": 0}
    x = np.asarray(data, dtype=np.float64).ravel()
    zero_frac = float(np.mean(np.abs(x) < 1e-12))
    rms = float(np.sqrt(np.mean(x * x)))
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    return {"zero_frac": zero_frac, "rms": rms, "peak": peak, "samples": len(x)}


def is_digital_silence(stats, min_sec=1.0, sample_rate=SAMPLE_RATE):
    """True si el audio es silencio DIGITAL: el sello de un microfono muerto o
    desenchufado es >50% de muestras exactamente en cero (en el caso real: 77%
    con vu_low=687) o RMS global < 5e-5 (ruido termico puro). Un audio de voz
    real o TTS tiene ~0% ceros y RMS > 0.01. Se exige >= min_sec de audio para
    no marcar clicks/transitorios de < 1s."""
    secs = stats.get("samples", 0) / sample_rate
    if secs < min_sec:
        return False
    return stats.get("zero_frac", 0.0) > 0.5 or stats.get("rms", 0.0) < 5e-5


# ═══════════════════════════════════════════════════════════════════════════════
# MOTORES DE TRANSCRIPCIÓN
# ═══════════════════════════════════════════════════════════════════════════════

class LocalWhisperEngine:
    """Motor de transcripción local con tiny/base/small.

    Backend dual (mejora #1):
      * "faster"  -> faster-whisper (CTranslate2, int8): ~5x mas rapido en
        CPU y menos RAM. No soporta deepcopy (objeto C++), asi que cada
        worker carga su propia instancia WhisperModel (cache global topeado).
      * "openai"  -> openai-whisper (torch): el exe compilado empaqueta
        modelos .pt de openai y NO incluye faster-whisper, asi que en modo
        frozen se fuerza "openai" (los .pt no los lee CTranslate2).
    Se auto-elige al instanciar: faster en desarrollo (si esta instalado),
    openai en el exe compilado. Se puede forzar con backend="...".
    """

    def __init__(self, model_name="base", language="es", backend=None):
        self.model_name = model_name
        # Idioma de transcripcion: "auto" = whisper detecta el idioma del audio
        # con detect_language; si no, un codigo ISO (es, en, pt, fr, ...) que
        # se fuerza en todos los chunks.
        self.language = (language or "es").strip().lower()
        self.backend = self._pick_backend(backend)
        self.model = None
        self.loading = False
        self.ready = False
        self.error = None
        # Puerta anti-congestión: cuando se cancela una transcripción paralela,
        # sus workers (con modelos deepcopy) siguen drenando su chunk actual.
        # Este evento queda limpio mientras un pool está activo o drenando, y
        # transcribe() espera a que se re-seteé antes de crear OTRO pool: evita
        # dos pools simultáneos (RAM duplicada y CPU saturada).
        self._drain_ev = threading.Event()
        self._drain_ev.set()
        # Caché de modelos entre corridas: deepcopies listas para reutilizar
        # (evita recargar + re-deepcopy por cada transcripción; baja el pico de
        # RAM y la latencia en transcripciones repetidas).
        self._model_cache = {}        # ruta -> [modelos listos]
        self._cache_order = []        # rutas por primer uso (eviccion LRU)
        self._cache_lock = threading.Lock()
        # Plantilla de carga: UNA carga de disco por ruta de modelo. La plantilla
        # NUNCA se transcribe directamente (solo se clona con deepcopy), asi que
        # no acumula hooks de kv_cache y cada clon queda aislado para el
        # paralelismo. Sin esto, el primer uso con N workers hacia N cargas de
        # disco simultaneas sobre el mismo .pt (lento y con traqueteo de disco).
        self._model_template = {}
        self._template_lock = threading.Lock()

    @staticmethod
    def _bundle_ct2_root():
        """Raiz de modelos CT2 empaquetados en el bundle (frozen) o None."""
        if not getattr(sys, "frozen", False):
            return None
        base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
        root = os.path.join(base, "models_ct2")
        return root if os.path.isdir(root) else None

    def _pick_backend(self, force=None):
        """Elige el backend de transcripcion."""
        if force in ("openai", "faster"):
            return force
        # Exe compilado: preferir faster-whisper si los modelos CT2 vienen
        # empaquetados (models_ct2/) y la dependencia esta; si no, openai
        # (compatibilidad con bundles anteriores que solo llevan .pt).
        if getattr(sys, "frozen", False):
            root = LocalWhisperEngine._bundle_ct2_root()
            if root is not None:
                try:
                    import faster_whisper  # noqa: F401
                    return "faster"
                except Exception:
                    pass
            return "openai"
        try:
            import faster_whisper  # noqa: F401
            return "faster"
        except Exception:
            return "openai"

    def _load_model_obj(self, path):
        """Carga una instancia del modelo segun el backend. faster-whisper usa
        CTranslate2 int8 (cpu_threads=1: un hilo por worker, igual que openai
        con set_num_threads(1), para no hacer oversubscription)."""
        if self.backend == "faster":
            from faster_whisper import WhisperModel
            return WhisperModel(path, device="cpu", compute_type="int8",
                                cpu_threads=1)
        import whisper
        return whisper.load_model(path)

    def _cache_get(self, path):
        """Toma un modelo listo del cache o None si no hay."""
        with self._cache_lock:
            lst = self._model_cache.get(path)
            if lst:
                return lst.pop()
        return None

    def _cache_put(self, path, mdl):
        """Devuelve un modelo al cache. Acotado por ruta (8) y por PRESUPUESTO
        GLOBAL (_MODEL_CACHE_MAX): si el usuario cambia de modelo, no acumular
        8 copias de cada ruta (8x75 + 8x142 + 8x466 MB = varios GB). Se evicta
        de la ruta de primer uso (LRU) cuando se excede el presupuesto."""
        with self._cache_lock:
            lst = self._model_cache.setdefault(path, [])
            if path not in self._cache_order:
                self._cache_order.append(path)
            if len(lst) < 8:
                lst.append(mdl)
            total = sum(len(v) for v in self._model_cache.values())
            while total > _MODEL_CACHE_MAX and self._cache_order:
                old = self._cache_order[0]
                ol = self._model_cache.get(old)
                if ol:
                    ol.pop()
                    total -= 1
                    if not ol:
                        self._model_cache.pop(old, None)
                        self._cache_order.pop(0)
                else:
                    self._cache_order.pop(0)

    def _resolve_model(self):
        """Devuelve la ruta del modelo empaquetado en el bundle (modo frozen,
        para funcionar sin internet) o el nombre del modelo (modo desarrollo,
        donde whisper usa su cache o lo descarga la primera vez)."""
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
            if self.backend == "faster":
                # faster-whisper: directorio CT2 (model.bin + tokenizer.json +
                # vocabulary.txt + config.json), autocontenido, sin internet.
                for name in (self.model_name, "tiny", "base"):
                    d = os.path.join(base, "models_ct2", name)
                    if os.path.isdir(d) and os.path.exists(os.path.join(d, "model.bin")):
                        # Si el modelo pedido no va empaquetado, cargamos tiny
                        # y actualizamos self.model_name para que el resultado
                        # no reporte un modelo distinto del realmente cargado.
                        self.model_name = name
                        return d
                return self.model_name  # sin CT2 empaquetado: nombre (descarga)
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
                self.model = self._load_model_obj(self._resolve_model())
                self.ready = True
                if callback:
                    callback("ready", self.model_name)
            except Exception as e:
                log_exc("carga del modelo local")
                self.error = str(e)
                if callback:
                    callback("error", str(e))
            finally:
                self.loading = False

        threading.Thread(target=_load, daemon=True).start()

    def transcribe(self, audio_path, timestamps=False, cancel_event=None,
                   progress_callback=None, check_silence=True, partial_callback=None):
        # Anti-congestión: si una transcripción anterior fue cancelada, su pool
        # sigue drenando workers con sus modelos deepcopy. Esperamos a que
        # termine antes de arrancar otra (el camino secuencial no crea pool,
        # solo espera si hay uno drenando). Sin esto, cancelar y volver a
        # transcribir creaba 2 pools simultáneos y el proceso se congestionaba.
        # Con tope de seguridad (90 s) y escape por cancelación: si el pool
        # previo se colgara, no bloqueamos al usuario para siempre.
        _drain_deadline = time.time() + 90.0
        _last_wait_msg = 0.0
        while not self._drain_ev.is_set() and time.time() < _drain_deadline:
            if cancel_event and cancel_event.is_set():
                return {"cancelled": True}
            now = time.time()
            if progress_callback and now - _last_wait_msg >= 1.0:
                _last_wait_msg = now
                progress_callback(0, 1,
                                  "Esperando a que terminen los hilos de la transcripción anterior...")
            self._drain_ev.wait(timeout=0.25)

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

        # ── Pre-validacion de silencio digital (mejora #2) ──────────────────
        # Si el WAV es silencio digital (microfono muerto/desenchufado: >50% de
        # muestras exactamente en cero, o RMS < 5e-5), NO gastar minutos de
        # transcripcion: se devuelve un aviso claro al instante. El flag
        # check_silence permite a los tests saltarse el chequeo.
        if check_silence:
            _stats = audio_silence_stats(data)
            if is_digital_silence(_stats):
                return {
                    "silence": True,
                    "text": "",
                    "segments": [],
                    "model": self.model_name,
                    "device": "cpu",
                    "chunks": 0,
                    "workers": 0,
                    "language": (self.language or "es").strip().lower(),
                    "silence_msg": (
                        "El audio parece SILENCIO DIGITAL ("
                        f"{_stats['zero_frac']*100:.0f}% de muestras en cero, "
                        f"RMS {_stats['rms']:.2e}). Revisa que el microfono este "
                        "conectado y capte voz; transcribir esto no daria texto."
                    ),
                }

        chunk_samples = int(30 * SAMPLE_RATE)
        # Overlap de 2s entre chunks: el audio del borde de cada ventana de 30s
        # se transcribe dos veces y se deduplica al unir, evitando cortes de
        # palabras justo en el límite del chunk. Coste ~7% más de cómputo.
        OVERLAP_S = 2.0
        step_samples = int((30 - OVERLAP_S) * SAMPLE_RATE)
        chunks, starts = [], []
        for i in range(0, len(data), step_samples):
            # Si lo que queda es SOLO el solapamiento (<= OVERLAP_S), esa parte
            # ya quedo transcrita por la ventana anterior: no crear un chunk
            # minusculo y redundante. Antes, un audio de 30s generaba 2 chunks
            # (30s + cola de 2s), forzaba el camino paralelo con un chunk casi
            # vacio al final, y ese chunk era propenso a que whisper alucinara
            # timestamps (bucle de seek). Se respeta el caso de audio muy corto
            # (< 2s) creando la primera ventana igualmente.
            if len(data) - i <= int(OVERLAP_S * SAMPLE_RATE) and chunks:
                break
            chunks.append(data[i:i + chunk_samples])
            starts.append(i / SAMPLE_RATE)
        total = len(chunks)
        if total == 0:
            return {"text": "", "segments": [], "model": self.model_name,
                    "device": "cpu", "chunks": 0, "backend": self.backend,
                    "language": (self.language or "es").strip().lower()}

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
        by_mem = max(1, min(8, int(1536 / mb)))   # piso: presupuesto base 1.5 GB
        free_mb = _free_ram_mb()
        if free_mb and free_mb >= 8192:
            # Solo en maquinas con RAM de sobra (>= 8 GB libres) se sube el
            # tope de workers hasta 16: coste real por copia ~3x el peso del
            # modelo (whisper mantiene buffers internos), presupuesto 35% de
            # la RAM libre. Nunca baja del piso de arriba y el resultado de la
            # transcripcion no cambia (mismos chunks, mismos modelos).
            by_mem = max(by_mem, min(16, int(free_mb * 0.35 / (mb * 3))))
        workers = max(1, min(cores, total, by_mem))
        # Nota de calidad: en paralelo cada chunk se transcribe de forma
        # independiente (condition_on_previous_text=False). Whisper solo
        # condiciona segmentos DENTRO de la misma llamada; en chunks de 30s
        # (1-3 segmentos) la perdida es despreciable y el initial_prompt
        # academico sigue anclando el estilo en cada chunk.

        PROMPT_ES = (
            "Esta es una transcripción de una clase universitaria o conferencia académica en español. "
            "El orador principal es el docente o conferencista. "
            "Ignora murmullos de fondo, interrupciones breves y preguntas sin respuesta del docente. "
            "Preserva datos duros: números, fechas, dosis, nomenclaturas técnicas y definiciones literales exactas. "
            "Transcribe fielmente solo lo dicho por el orador principal."
        )
        PROMPT_EN = (
            "This is a transcription of a university lecture or academic conference. "
            "The main speaker is the lecturer or presenter. "
            "Ignore background murmurs, brief interruptions and questions the lecturer does not answer. "
            "Preserve hard facts: numbers, dates, dosages, technical nomenclature and literal definitions exactly. "
            "Transcribe faithfully only what the main speaker said."
        )

        # Idioma de transcripcion: self.language ("auto" = deteccion por
        # whisper sobre el primer chunk; si no, codigo ISO forzado). _lang y
        # _prompt se resuelven UNA vez (camino secuencial tras cargar el
        # modelo; camino paralelo antes de crear el pool) y se aplican a TODOS
        # los chunks, para que la transcripcion completa salga en un solo
        # idioma (whisper detectaria por chunk y podria alternar es/en).
        _lang = "es"
        _prompt = PROMPT_ES

        def _resolve_lang(mdl, audio):
            """Resuelve (idioma, prompt) segun self.language. En modo 'auto'
            usa la deteccion del backend sobre el audio; si falla, asume 'es'."""
            nonlocal _lang, _prompt
            cfg = getattr(self, "language", "es") or "es"
            cfg = str(cfg).strip().lower()
            if cfg == "auto":
                try:
                    if self.backend == "faster":
                        # faster-whisper: la deteccion viene en info.language
                        # de una pasada con language=None (barata, ~0.7s).
                        # initial_prompt=None: un prompt en espanol durante la
                        # deteccion podria sesgar el idioma detectado.
                        _segs, _info = mdl.transcribe(
                            audio, language=None, task="transcribe",
                            beam_size=5, initial_prompt=None,
                            condition_on_previous_text=False,
                            without_timestamps=True,
                        )
                        lang = (getattr(_info, "language", None) or "es").strip().lower()
                        # El generador no se consume: la deteccion ya ocurrio
                        # y el decode real lo hara _transcribe_with por chunk.
                    else:
                        import whisper as _w
                        mel = _w.log_mel_spectrogram(audio)
                        probs = mdl.detect_language(mel)
                        # whisper devuelve (tokens, {lang: prob}) en la version
                        # 20250625 (verificado en el log: AttributeError en modo
                        # auto porque el dict iba en el indice 1 de una tupla y
                        # max() llamaba .get sobre la tupla). Se aceptan ambos
                        # formatos: dict a secas o tupla cuyo indice 1 es el dict.
                        if isinstance(probs, tuple) and probs and isinstance(probs[1], dict):
                            probs = probs[1]
                        lang = max(probs, key=probs.get) if probs else "es"
                except Exception:
                    log_exc("deteccion de idioma (modo auto)")
                    lang = "es"
            else:
                lang = cfg
            _lang = lang
            _prompt = PROMPT_ES if lang == "es" else PROMPT_EN
            return lang

        def _transcribe_with(mdl, chunk, use_cond):
            # Se pasa el array float32 directamente a Whisper (sin escribir
            # WAV temporal): evita depender de ffmpeg y funciona offline.
            # verbose=None (NO False): con False, whisper 20250625 ACTIVA una
            # barra tqdm que escribe a sys.stdout; en el exe compilado con
            # console=False sys.stdout es None y tqdm reventaba con
            # AttributeError ('NoneType' object has no attribute 'write') en
            # el primer worker -> la transcripcion fallaba al instante (bug
            # confirmado en ~/AudioClass_Recordings/logs/audioclass.log).
            if self.backend == "faster":
                segs, _info = mdl.transcribe(
                    chunk, language=_lang, task="transcribe",
                    beam_size=5, initial_prompt=_prompt,
                    condition_on_previous_text=use_cond,
                    without_timestamps=not timestamps,
                )
                seg_list = [
                    {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
                    for s in segs
                ]
                return {
                    "text": " ".join(s["text"] for s in seg_list if s["text"]),
                    "segments": seg_list,
                }
            return mdl.transcribe(
                chunk, language=_lang, task="transcribe",
                fp16=False, verbose=None,
                condition_on_previous_text=use_cond,
                initial_prompt=_prompt
            )

        if workers == 1:
            # ── Camino secuencial (1 chunk, 1 nucleo o modelo grande) ─────────
            from concurrent.futures import ThreadPoolExecutor as _TPE
            if self.model is None:
                self.model = self._load_model_obj(self._resolve_model())
            # Idioma: detectar UNA vez con el primer chunk (modo auto) y
            # aplicarlo a todos los chunks (consistencia).
            _resolve_lang(self.model, chunks[0])

            parts, segs = [], []
            chunk_times = []       # tiempos reales -> media movil (ultimos 3)
            est_dur = CHUNK_EST_SEED   # seed del 1er chunk: 1x su duracion (30s)
            chunks_omitidos = 0    # chunks descartados por timeout de whisper
            for i, chunk in enumerate(chunks, 1):
                if cancel_event and cancel_event.is_set():
                    return {"cancelled": True}
                if self.model is None:
                    # Un chunk anterior pudo omitirse por timeout (whisper
                    # colgado): el hilo huerfano sigue usando el modelo viejo,
                    # asi que se carga uno NUEVO para no transcribir encima.
                    self.model = self._load_model_obj(self._resolve_model())
                if progress_callback:
                    progress_callback(i - 1, total, f"Procesando chunk {i}/{total}...")

                # Whisper no reporta progreso dentro del chunk: un hilo auxiliar
                # estima el avance con la media movil del tiempo por chunk.
                stop = threading.Event()
                t0 = time.time()

                def _report(i=i, t0=t0, est=est_dur, stop=stop):
                    # Tope 0.99 (no 0.95): antes la barra se estancaba en ~94-95%
                    # cuando el chunk superaba la estimacion (maquina lenta).
                    while not stop.is_set():
                        el = time.time() - t0
                        frac = min(el / est, 0.99) if est > 0 else 0.0
                        if stop.is_set():
                            break
                        if progress_callback:
                            pct = int((i - 1 + frac) / total * 100)
                            if el <= est:
                                rem = max(0, int(est - el))
                            else:
                                # El chunk ya supero la media: el restante no se
                                # congela en 0, se estima desde el tiempo real.
                                rem = max(1, int(el * 0.12))
                            progress_callback(i - 1 + frac, total,
                                              f"Chunk {i}/{total} · {pct}% · ~{rem}s rest")
                        stop.wait(0.25)

                rthread = threading.Thread(target=_report, daemon=True)
                rthread.start()

                # Tope de seguridad por chunk: si whisper se cuelga (bucle de
                # timestamps sin avanzar en la misma ventana), no esperar
                # horas. Presupuesto holgado: max(120s, 4x la media real por
                # chunk); nunca afecta a maquinas lentas normales (tiny/base
                # terminan un chunk de 30s en < 60s).
                _budget = max(CHUNK_BUDGET_FLOOR, est_dur * 4.0)
                _tp = _TPE(max_workers=1)
                try:
                    try:
                        _fut = _tp.submit(_transcribe_with, self.model, chunk, True)
                        result = _fut.result(timeout=_budget)
                    except TimeoutError:
                        # Whisper colgado: se omite el chunk. El hilo huerfano
                        # queda en daemon drenando solo; se invalida self.model
                        # para que el siguiente chunk cargue uno limpio (los
                        # hooks de kv_cache de whisper no son thread-safe).
                        result = {}
                        chunks_omitidos += 1
                        self.model = None
                        log_info(f"chunk {i}/{total} omitido: whisper no termino "
                                 f"en {_budget:.0f}s (posible bucle de timestamps)")
                finally:
                    stop.set()
                    rthread.join(timeout=1.0)
                    _tp.shutdown(wait=False)

                # Solo se registra el tiempo de chunks EXITOSOS: si uno colgo y
                # se omitio, su duracion (= presupuesto, p. ej. 120s) inflaria
                # la media movil y el presupuesto del siguiente chunk se
                # multiplicaria x4 del tiempo de cuelgue (120s -> 480s). El
                # camino paralelo hace lo mismo (los abandonados no entran en
                # `times`).
                if result:
                    chunk_times.append(time.time() - t0)
                    est_dur = float(np.mean(chunk_times[-3:]))

                if progress_callback:
                    progress_callback(i, total, f"Chunk {i}/{total} listo")

                if result.get("text"):
                    parts.append(result["text"].strip())
                    # Streaming (mejora #3): texto parcial acumulado en vivo.
                    if partial_callback:
                        try:
                            partial_callback(" ".join(parts))
                        except Exception:
                            log_exc("streaming de texto parcial (secuencial)")
                if timestamps and "segments" in result:
                    # Dedupe del overlap: descartar segmentos de la zona
                    # solapada salvo en el último chunk (se transcribieron ya
                    # en el chunk anterior).
                    limit = starts[i - 1] + (30 - OVERLAP_S)
                    if i == total or total == 1:
                        segs_local = result["segments"]
                    else:
                        segs_local = [s for s in result["segments"] if s.get("start", 0) < limit - starts[i - 1]]
                    for s in segs_local:
                        sc = dict(s)
                        sc["start"] += starts[i - 1]
                        sc["end"] += starts[i - 1]
                        segs.append(sc)

            if chunks_omitidos == total and total > 0 and not parts:
                raise RuntimeError(
                    f"Whisper no pudo transcribir el audio: {total}/{total} chunks "
                    "omitidos por timeout (whisper colgado). Revisa el modelo y el log."
                )

            return {
                "text": " ".join(parts),
                "segments": segs,
                "model": self.model_name,
                "device": "cpu",
                "chunks": total,
                "workers": 1,
                "language": _lang,
                "backend": self.backend,
                "chunks_omitidos": chunks_omitidos
            }

        # ── Camino PARALELO: un modelo Whisper POR WORKER (thread-local) ──────
        # Nota: faster-whisper (CTranslate2) no soporta deepcopy y ya limita
        # sus hilos con cpu_threads=1; openai-whisper (torch) necesita
        # set_num_threads(1) para no hacer oversubscription con N workers.
        _is_faster = self.backend == "faster"
        import copy
        from concurrent.futures import ThreadPoolExecutor, wait as _cf_wait
        if not _is_faster:
            import torch
            prev_threads = torch.get_num_threads()
            torch.set_num_threads(1)

        results = {}     # indice -> resultado (acceso bajo lock)
        started = {}     # indice -> t0 real de inicio del worker
        times = []       # tiempos reales por chunk -> media movil (ultimos 3)
        est = [CHUNK_EST_SEED]     # seed del 1er chunk: 1x su duracion (30s)
        last_num = [0.0] # maximo reportado: la barra nunca retrocede
        lock = threading.Lock()
        stop = threading.Event()
        _local = threading.local()
        _model_path = self._resolve_model()

        def _get_model():
            """Toma un modelo listo del cache o carga uno nuevo si no hay.

            Backend openai: la copia queda aislada de cualquier cache interno
            de whisper (los hooks de kv_cache se instalan sobre el modelo
            compartido y romperian la transcripcion concurrente). Cache FRIO
            (1a transcripcion de la sesion): en vez de N cargas de disco
            simultaneas (una por worker) se carga UNA plantilla bajo candado y
            los workers clonan de ella en RAM (deepcopy). La plantilla nunca se
            transcribe directamente, asi que no acumula hooks y sus clones
            siempre salen limpios.

            Backend faster: CTranslate2 no soporta deepcopy, asi que cada
            worker carga SU PROPIA instancia WhisperModel (int8, cpu_threads=1)
            desde disco; el cache global (tope _MODEL_CACHE_MAX) reutiliza las
            instancias entre corridas. La carga es ~1-5s por instancia y la
            primera corrida paga N cargas; el resto paga cache."""
            mdl = self._cache_get(_model_path)
            if mdl is not None:
                return mdl
            if _is_faster:
                return self._load_model_obj(_model_path)
            import whisper
            with self._template_lock:
                mdl = self._cache_get(_model_path)
                if mdl is not None:
                    return mdl
                tmpl = self._model_template.get(_model_path)
                if tmpl is None:
                    tmpl = whisper.load_model(_model_path)
                    # Presupuesto: conservar SOLO la plantilla de la ruta actual.
                    # Si el usuario cambia tiny->base->small en una sesion, no
                    # acumular 3 plantillas (varios GB) fuera del tope LRU: al
                    # crear una nueva se evictan las anteriores. Volver a una
                    # ruta evictada solo paga una carga de disco (el
                    # comportamiento base previo a esta optimizacion).
                    self._model_template.clear()
                    self._model_template[_model_path] = tmpl
                return copy.deepcopy(tmpl)

        def _put_model(mdl):
            """Devuelve el modelo al cache (tope por ruta + presupuesto global)."""
            self._cache_put(_model_path, mdl)

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
                    frac_sum += min((now - t0) / est[0], 0.99) if est[0] > 0 else 0.0
                # Lectura/escritura de last_num bajo lock: ambos hilos (este y
                # el bucle principal) la comparten, y asi la monotonia es
                # estricta sin micro-carreras. min(total) evita que la suma de
                # fracciones estimadas supere el 100% por redondeo.
                with lock:
                    num = min(total, max(last_num[0], done + frac_sum))
                    last_num[0] = num
                pct = int(num / total * 100)
                rem = max(0, int((total - done) / workers * est[0]))
                if progress_callback:
                    progress_callback(num, total,
                                      f"⚡ {workers} núcleos · {done}/{total} chunks · {pct}% · ~{rem}s rest")
                stop.wait(0.25)

        def _transcribe_one(idx, chunk):
            # El modelo se ADQUIERE dentro de la tarea (no se pre-asigna por
            # indice): con mas chunks que workers, pre-asignar models[i%workers]
            # hacia que una futura corrida pudiera reutilizar el MISMO objeto
            # para dos chunks concurrentes (el KeyError de kv_cache que el
            # deepcopy evita). Al adquirir aqui, cada tarea en curso toma un
            # modelo distinto del cache y lo devuelve al terminar.
            mdl = _get_model()
            with lock:
                started[idx] = time.time()
            try:
                return idx, _transcribe_with(mdl, chunk, False)
            finally:
                _put_model(mdl)

        # Idioma: en modo auto, detectar UNA vez con un modelo del cache y
        # aplicarlo a TODOS los chunks (consistencia; evita que cada worker
        # detecte por su cuenta y alternen es/en). Solo se adquiere modelo si
        # hace falta detectar (idioma forzado no lo requiere), y si la carga o
        # deteccion falla se degrada a 'es' en vez de propagar una excepcion
        # cruda desde el hilo principal (el bucle de futuros tiene su propia
        # red de seguridad por chunk; esta deteccion ocurre ANTES de el).
        if (getattr(self, "language", "es") or "es").strip().lower() == "auto":
            try:
                _probe = _get_model()
                try:
                    _resolve_lang(_probe, chunks[0])
                finally:
                    _put_model(_probe)
            except Exception:
                log_exc("deteccion de idioma (modo auto)")
                _lang, _prompt = "es", PROMPT_ES

        try:
            self._drain_ev.clear()
            pool = ThreadPoolExecutor(max_workers=workers)
        except Exception:
            self._drain_ev.set()  # si falla la creación, liberar la puerta
            raise
        futures = [pool.submit(_transcribe_one, i, ch) for i, ch in enumerate(chunks)]
        rthread = threading.Thread(target=_report, daemon=True)
        rthread.start()

        cancelled = False
        skipped = []       # chunks omitidos por timeout o error (whisper colgado)
        skipped_err = []   # subconjunto de skipped que fallaron con excepcion
        fut_index = {f: i for i, f in enumerate(futures)}
        fut_start = {f: time.time() for f in futures}
        try:
            pending = set(futures)
            while pending:
                done, _ = _cf_wait(pending, timeout=0.5)
                now = time.time()
                for fut in list(done):
                    pending.discard(fut)
                    if cancel_event and cancel_event.is_set():
                        cancelled = True
                        break
                    try:
                        idx, result = fut.result()
                    except Exception as e:
                        # Un chunk que falla (p. ej. modelo corrupto) NO tumba
                        # toda la transcripcion: se omite y se sigue con el
                        # resto (antes se abortaba todo con una excepcion).
                        skipped.append(fut_index[fut])
                        skipped_err.append(fut_index[fut])
                        log_info(f"chunk {fut_index[fut]} con error, se omite: {e!r}")
                        continue
                    with lock:
                        started_t0 = started.get(idx)
                        results[idx] = result
                    if started_t0 is not None:
                        with lock:
                            times.append(time.time() - started_t0)
                            est[0] = float(np.mean(times[-3:]))
                    if progress_callback:
                        with lock:
                            done_n = len(results)
                            # Clamp al maximo reportado: el reporter puede
                            # haber avanzado hasta done + 0.95 x chunks en
                            # curso, y un mensaje con done entero haria la
                            # barra RETROCEDER.
                            num = max(last_num[0], float(done_n))
                            last_num[0] = num
                        progress_callback(num, total, f"{done_n}/{total} chunks listos")
                    if partial_callback:
                        try:
                            with lock:
                                _partial = " ".join(
                                    results[i].get("text", "").strip()
                                    for i in range(total) if i in results
                                    and results[i].get("text")
                                )
                            if _partial.strip():
                                partial_callback(_partial)
                        except Exception:
                            log_exc("streaming de texto parcial (paralelo)")
                if cancelled:
                    break
                # ── Tope por chunk ──────────────────────────────────────────
                # Si whisper se cuelga (bucle de timestamps sin avanzar en la
                # misma ventana de 30s), NO esperar horas: se abandona ese
                # chunk y se sigue con el resto. Presupuesto holgado: max(piso,
                # 4x la media real por chunk), asi que nunca afecta a maquinas
                # lentas normales. Para un futuro AUN en cola (no empezo a
                # transcribirse porque todos los workers estan ocupados) se usa
                # su antiguedad desde el submit; si ademas lleva mas del
                # presupuesto esperando, es que todos los workers estan
                # colgados y hay que salir igualmente.
                with lock:
                    _est = est[0] if times else CHUNK_EST_SEED
                _budget = max(CHUNK_BUDGET_FLOOR, _est * 4.0)
                for fut in list(pending):
                    _idx = fut_index[fut]
                    with lock:
                        _st = started.get(_idx)
                    if _st is not None:
                        _age = now - _st          # transcribiendose desde _st
                    else:
                        _age = now - fut_start[fut]  # esperando en cola
                    if _age > _budget:
                        pending.discard(fut)
                        skipped.append(_idx)
                        with lock:
                            started.pop(_idx, None)
                        log_info(f"chunk {_idx} omitido por presupuesto "
                                 f"({_budget:.0f}s): whisper no respondio")
        finally:
            stop.set()
            rthread.join(timeout=1.0)
            if cancelled or skipped:
                # Whisper no es interrumpible a mitad de chunk: los workers en
                # curso (incluidos los colgados) terminan solos en un hilo
                # daemon (sin bloquear la UI) y _drain_ev impide que la
                # siguiente transcripcion arranque hasta liberar RAM/CPU (el
                # arranque de transcribe tiene tope de 90s de espera).
                pool.shutdown(wait=False, cancel_futures=True)
                threading.Thread(
                    target=lambda p=pool: (p.shutdown(wait=True), self._drain_ev.set()),
                    daemon=True,
                ).start()
            else:
                pool.shutdown(wait=True)
                self._drain_ev.set()
            if not _is_faster:
                torch.set_num_threads(prev_threads)

        if cancelled:
            return {"cancelled": True}
        # Si NINGUN chunk pudo transcribirse (todo error o todo timeout), es un
        # fallo real: se reporta como ERROR en vez de devolver un texto vacio
        # "exitoso". El texto parcial solo se devuelve cuando al menos un chunk
        # funciono.
        if not results and skipped:
            if len(skipped_err) == len(skipped):
                _razon = f"todos los chunks fallaron con error ({len(skipped)}/{total})"
            elif skipped_err:
                _razon = f"errores y timeouts ({len(skipped)}/{total} chunks omitidos)"
            else:
                _razon = (f"{len(skipped)}/{total} chunks omitidos por timeout "
                          "(whisper colgado en este audio)")
            raise RuntimeError(f"Transcripcion local fallida: {_razon}. "
                               "Revisa el modelo y el log (audioclass.log).")

        # Reconstruir en ORDEN original (los chunks terminan desordenados)
        parts, segs = [], []
        for i in range(total):
            r = results.get(i)
            if not r:
                continue
            if r.get("text"):
                parts.append(r["text"].strip())
            if timestamps and "segments" in r:
                # Dedupe del overlap: descartar los segmentos de la zona
                # solapada (los ultimos OVERLAP_S s del chunk, que ya se
                # transcribieron en el chunk siguiente). Se conserva el texto
                # de la ventana nominal de 30s de cada chunk.
                segs_local = r["segments"]
                if i < total - 1:
                    limit_local = 30.0 - OVERLAP_S
                    segs_local = [s for s in segs_local if s.get("start", 0) < limit_local]
                for s in segs_local:
                    sc = dict(s)
                    sc["start"] += starts[i]
                    sc["end"] += starts[i]
                    segs.append(sc)

        return {
            "text": " ".join(parts),
            "segments": segs,
            "model": self.model_name,
            "device": "cpu",
            "chunks": total,
            "workers": workers,
            "language": _lang,
            "backend": self.backend,
            "chunks_omitidos": len(skipped)
        }


class CloudColabEngine:
    """Motor de transcripción vía Google Colab (Medium/Large)."""

    def __init__(self, url="", api_key="audioclass", language="es"):
        self.url = url.rstrip("/") if url else ""
        self.api_key = api_key
        # Idioma pedido al servidor: "auto" delega la deteccion al whisper
        # del servidor (language=None); si no, codigo ISO forzado.
        self.language = (language or "es").strip().lower()
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
            data = {"key": self.api_key, "language": self.language}

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

    PROVIDER = "Gemini"

    def __init__(self, api_key="", model="flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _model_name(self):
        """Resuelve el alias (flash/pro) al ID de modelo Gemini actual."""
        return self.GEMINI_MODELS.get(self.model, "gemini-2.0-flash")

    def _call(self, prompt, max_tokens, temperature, timeout=120):
        """Una llamada a la API del proveedor. Devuelve {'text': ...} o {'error': ...}."""
        import requests
        model_name = self._model_name()
        url = f"{self.base_url}/{model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.9
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=timeout)
        except Exception as e:
            return {"error": f"Error {self.PROVIDER}: {e}"}
        if r.status_code != 200:
            return {"error": f"{self.PROVIDER} HTTP {r.status_code}: {r.text[:300]}"}
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return {"error": f"{self.PROVIDER} no generó respuesta"}
        return {"text": candidates[0]["content"]["parts"][0]["text"]}

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
        """Adapta texto usando el proveedor. Segmenta automáticamente si es muy largo."""
        import requests

        if template_name not in self.TEMPLATES:
            return {"error": f"Template '{template_name}' no existe"}

        template = self.TEMPLATES[template_name]
        model_name = self._model_name()

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

                res = self._call(chunk_prompt, 2048, template.get("temperature", 0.3), timeout=60)
                if "error" in res:
                    return {"error": f"Error en chunk {i+1}: {res['error']}"}
                partial_results.append(res["text"])

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

            result = self._call(final_prompt, template.get("max_tokens", 4096),
                                template.get("temperature", 0.2))
        else:
            # Texto corto: proceso directo con prompt completo
            prompt = template["prompt"].replace("{TEXT}", text)
            if progress_callback:
                progress_callback(2, 3, f"Generando con {self.PROVIDER}...")
            result = self._call(prompt, template.get("max_tokens", 4096),
                                template.get("temperature", 0.3))

        if "error" in result:
            return result

        if progress_callback:
            progress_callback(3, 3, "¡Listo!")

        return {
            "text": result["text"],
            "template": template_name,
            "model": model_name,
            "icon": template["icon"],
            "provider": self.PROVIDER
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# MOTOR DE ADAPTACIÓN INTELIGENTE (OPENAI API) — alternativa a Gemini
# ═══════════════════════════════════════════════════════════════════════════════

class OpenAIAdaptationEngine(GeminiAdaptationEngine):
    """Adapta transcripciones usando OpenAI (Chat Completions / GPT).

    Misma interfaz que GeminiAdaptationEngine (test_key + adapt) y reutiliza
    los mismos TEMPLATES, pero llama a la API de OpenAI (api.openai.com).
    """

    PROVIDER = "OpenAI"

    # Aliases de modelo: mini = rapido y economico | gpt4o = maxima calidad
    OPENAI_MODELS = {
        "mini": "gpt-4o-mini",
        "gpt4o": "gpt-4o",
    }

    def __init__(self, api_key="", model="mini"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    def _model_name(self):
        return self.OPENAI_MODELS.get(self.model, "gpt-4o-mini")

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def _call(self, prompt, max_tokens, temperature, timeout=120):
        import requests
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self._model_name(),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            r = requests.post(url, json=payload, headers=self._headers(), timeout=timeout)
        except Exception as e:
            return {"error": f"Error {self.PROVIDER}: {e}"}
        if r.status_code != 200:
            detail = ""
            try:
                detail = r.json().get("error", {}).get("message", "")
            except Exception:
                pass
            return {"error": f"{self.PROVIDER} HTTP {r.status_code}: {detail or r.text[:300]}"}
        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            return {"error": f"{self.PROVIDER} no generó respuesta"}
        content = (choices[0].get("message") or {}).get("content") or ""
        return {"text": content}

    def test_key(self):
        if not self.api_key or len(self.api_key) < 10:
            return False, "API Key no configurada"
        try:
            import requests
        except ImportError:
            return False, "Falta el paquete 'requests' (pip install requests)"
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(), timeout=15)
            if r.status_code == 200:
                return True, "API Key válida"
            detail = ""
            try:
                detail = r.json().get("error", {}).get("message", "")
            except Exception:
                pass
            if r.status_code == 401:
                return False, "Sin autenticación (401): revisa que la API Key sea válida"
            if r.status_code == 403:
                return False, "Permiso denegado (403): revisa tu cuenta de OpenAI"
            if r.status_code == 429:
                return False, "Límite de cuota superado (429). Espera o revisa tu plan."
            if r.status_code >= 500:
                return False, "Error del servidor de OpenAI. Intenta más tarde."
            msg = detail or f"Error HTTP {r.status_code}"
            return False, f"{msg} (HTTP {r.status_code})"
        except requests.exceptions.Timeout:
            return False, "Tiempo de espera agotado. Revisa tu conexión a internet."
        except requests.exceptions.ConnectionError:
            return False, "No se pudo conectar con OpenAI. Revisa tu conexión a internet."
        except Exception as e:
            return False, f"Error inesperado: {e}"


def build_adaptation_engine(provider="gemini", gemini_api_key="", gemini_model="flash",
                            openai_api_key="", openai_model="mini"):
    """Devuelve el motor de adaptacion segun el proveedor elegido por el usuario."""
    if provider == "openai":
        return OpenAIAdaptationEngine(openai_api_key, openai_model)
    return GeminiAdaptationEngine(gemini_api_key, gemini_model)


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


