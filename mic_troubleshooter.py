#!/usr/bin/env python3
"""
mic_troubleshooter.py — Sistema Multiplataforma de Diagnóstico y Reparación de Micrófono
========================================================================================
Diagnostica, evalúa acústicamente y corrige problemas de micrófono en:
  - Linux: PipeWire (wpctl), PulseAudio (pactl) y ALSA (amixer)
  - Windows: CoreAudio (IAudioEndpointVolume, IAudioMute, Boost)
  - macOS: osascript (volumen de entrada y control de audio)

Capacidades principales:
  1. Detección automática del servidor/backend de audio del sistema operativo.
  2. Consulta de nivel (%), ganancia (dB) y estado de mute.
  3. Desmuteo y ajuste automático de volumen al 100% u óptimo.
  4. Verificación de compatibilidad de tasa de muestreo (16 kHz vs tasa nativa ALSA/hardware).
  5. Prueba acústica en vivo (ruido de fondo, voz p90, SNR, hum 50/60Hz, clipping y silencio digital).
  6. auto_fix() unificado con informe estructurado de acciones realizadas.
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    from scipy import signal
except Exception:
    signal = None


# ── Constantes y Umbrales Acústicos ──────────────────────────────────────────
SAMPLE_RATE = 16000
BLOCK_SIZE = 800  # 50 ms a 16 kHz

RMS_SILENCE = 0.005  # p90 < 0.005 -> Silencio digital o mic desconectado
RMS_VERY_LOW = 0.02  # p90 < 0.02 -> Extremadamente bajo (riesgo alto de transcripción vacía)
RMS_WEAK = 0.04  # p90 < 0.04 -> Señal débil (pérdida de palabras suaves)
RMS_OPTIMAL = 0.10  # p90 >= 0.10 -> Nivel ideal para ASR
CLIP_THRESHOLD = 0.99  # Muestras >= 0.99 indican saturación/recorte
SNR_MIN_DB = 12.0  # SNR < 12 dB indica ambiente ruidoso


@dataclass
class MicState:
    """Estado actual del micrófono en el sistema operativo."""

    device_name: str = ""
    volume: int = 0  # 0 - 100%
    is_muted: bool = False
    db: float | None = None  # Nivel en dB si está disponible
    backend: str = "unknown"  # pipewire, pulseaudio, alsa, windows, macos, unknown
    status: str = "OK"  # OK, MUTED, LOW_VOLUME, UNAVAILABLE
    details: str = ""


@dataclass
class AcousticMetrics:
    """Resultados del análisis acústico de una señal de audio."""

    dur: float = 0.0
    piso: float = 0.0  # Piso de ruido (percentil 10)
    p90: float = 0.0  # Nivel de voz (percentil 90)
    peak: float = 0.0  # Pico absoluto
    rms: float = 0.0  # RMS global
    snr_db: float = 0.0  # Relación señal/ruido en dB
    clipping_pct: float = 0.0  # Porcentaje de muestras saturadas
    hum_detected: bool = False  # Detección de zumbido de 50/60 Hz
    is_digital_silence: bool = False
    verdict: str = "OK"  # OPTIMAL, WEAK, VERY_LOW, CLIPPING, NOISY, SILENCE, ERROR
    recommendations: list[str] = field(default_factory=list)


def detect_backend() -> str:
    """Detecta el servidor o subsistema de audio activo en el sistema."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        # Prioridad 1: PipeWire (WirePlumber / wpctl)
        if shutil.which("wpctl"):
            try:
                res = subprocess.run(
                    ["wpctl", "status"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0 and "PipeWire" in res.stdout:
                    return "pipewire"
            except Exception:
                pass

        # Prioridad 2: PulseAudio (pactl)
        if shutil.which("pactl"):
            try:
                res = subprocess.run(
                    ["pactl", "info"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    return "pulseaudio"
            except Exception:
                pass

        # Prioridad 3: ALSA (amixer)
        if shutil.which("amixer"):
            return "alsa"

    return "unknown"


# ── Resampling Polifásico de Alta Eficiencia ─────────────────────────────────
def resample_audio(data: np.ndarray, orig_sr: int, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    """Remuestrea un array 1D de audio usando filtrado polifásico (sin FFT gigante)."""
    if orig_sr == target_sr:
        return data.astype(np.float32)
    if len(data) == 0:
        return np.zeros(0, dtype=np.float32)

    g = math.gcd(int(orig_sr), int(target_sr))
    up = target_sr // g
    down = orig_sr // g

    if signal is not None and up <= 1000 and down <= 1000:
        return signal.resample_poly(data, up, down).astype(np.float32)
    elif signal is not None:
        num = round(len(data) * target_sr / orig_sr)
        return signal.resample(data, num).astype(np.float32)
    else:
        # Fallback por interpolación lineal si scipy no estuviera disponible
        orig_indices = np.linspace(0, len(data) - 1, len(data))
        num = round(len(data) * target_sr / orig_sr)
        target_indices = np.linspace(0, len(data) - 1, num)
        return np.interp(target_indices, orig_indices, data).astype(np.float32)


# ── Detección de Zumbido Eléctrico (50 Hz / 60 Hz) ──────────────────────────
def detect_mains_hum(data: np.ndarray, sr: int = SAMPLE_RATE) -> bool:
    """Detecta la presencia de zumbido eléctrico típico (50 Hz en Europa/Latam o 60 Hz en EEUU)."""
    if len(data) < sr * 0.5:
        return False
    try:
        # FFT sobre 1 segundo o longitud disponible
        n = min(len(data), sr * 2)
        segment = data[:n]
        fft_vals = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
        freqs = np.fft.rfftfreq(len(segment), 1.0 / sr)

        def band_power(f_center, delta=2.5):
            mask = (freqs >= f_center - delta) & (freqs <= f_center + delta)
            return float(np.sum(fft_vals[mask] ** 2)) if np.any(mask) else 0.0

        p50 = band_power(50.0)
        p60 = band_power(60.0)
        p_ref = band_power(110.0) + band_power(35.0) + 1e-9

        # Si 50Hz o 60Hz tiene al menos 12 dB más de energía que la banda vecina
        ratio50 = p50 / p_ref
        ratio60 = p60 / p_ref
        return bool(ratio50 > 4.0 or ratio60 > 4.0)
    except Exception:
        return False


# ── Inspección y Control de Micrófono por Backend ───────────────────────────


def _get_linux_pipewire_state() -> MicState:
    """Consulta nivel y mute vía wpctl."""
    state = MicState(backend="pipewire")
    try:
        res = subprocess.run(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        out = res.stdout.strip()
        state.details = out
        # Formatos comunes: 'Volume: 0.27', 'Volume: 0.27 [MUTED]'
        m = re.search(r"Volume:\s*([0-9.]+)", out)
        if m:
            vol_val = float(m.group(1))
            state.volume = round(vol_val * 100)
        state.is_muted = "[MUTED]" in out.upper()

        if state.is_muted:
            state.status = "MUTED"
        elif state.volume < 40:
            state.status = "LOW_VOLUME"
        else:
            state.status = "OK"
    except Exception as e:
        state.status = "UNAVAILABLE"
        state.details = f"wpctl error: {e}"
    return state


def _set_linux_pipewire(volume: int | None = None, unmute: bool = True) -> bool:
    """Aplica volumen y unmute con wpctl."""
    ok = True
    try:
        if unmute:
            res = subprocess.run(
                ["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0"],
                capture_output=True,
                timeout=2,
            )
            if res.returncode != 0:
                ok = False
        if volume is not None:
            vol_val = max(0.0, min(1.5, volume / 100.0))
            res = subprocess.run(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", str(vol_val)],
                capture_output=True,
                timeout=2,
            )
            if res.returncode != 0:
                ok = False
    except Exception:
        return False
    return ok


def _get_linux_pulseaudio_state() -> MicState:
    """Consulta nivel y mute vía pactl."""
    state = MicState(backend="pulseaudio")
    try:
        r_vol = subprocess.run(
            ["pactl", "get-source-volume", "@DEFAULT_SOURCE@"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        r_mute = subprocess.run(
            ["pactl", "get-source-mute", "@DEFAULT_SOURCE@"],
            capture_output=True,
            text=True,
            timeout=2,
        )

        out_vol = r_vol.stdout.strip()
        state.details = out_vol

        # Buscar porcentaje: 'front-left: ... / 27% / -33.69 dB'
        m_pct = re.search(r"(\d+)%", out_vol)
        if m_pct:
            state.volume = int(m_pct.group(1))

        # Buscar dB
        m_db = re.search(r"([-+]?\d+[\.,]?\d*)\s*dB", out_vol)
        if m_db:
            try:
                state.db = float(m_db.group(1).replace(",", "."))
            except Exception:
                pass

        state.is_muted = "yes" in r_mute.stdout.lower()

        if state.is_muted:
            state.status = "MUTED"
        elif state.volume < 40:
            state.status = "LOW_VOLUME"
        else:
            state.status = "OK"
    except Exception as e:
        state.status = "UNAVAILABLE"
        state.details = f"pactl error: {e}"
    return state


def _set_linux_pulseaudio(volume: int | None = None, unmute: bool = True) -> bool:
    """Aplica volumen y unmute con pactl."""
    ok = True
    try:
        if unmute:
            res = subprocess.run(
                ["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "0"],
                capture_output=True,
                timeout=2,
            )
            if res.returncode != 0:
                ok = False
        if volume is not None:
            vol_pct = max(0, min(150, volume))
            res = subprocess.run(
                ["pactl", "set-source-volume", "@DEFAULT_SOURCE@", f"{vol_pct}%"],
                capture_output=True,
                timeout=2,
            )
            if res.returncode != 0:
                ok = False
    except Exception:
        return False
    return ok


def _get_linux_alsa_state() -> MicState:
    """Consulta nivel y mute vía amixer."""
    state = MicState(backend="alsa")
    try:
        res = subprocess.run(
            ["amixer", "sget", "Capture"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        out = res.stdout.strip()
        state.details = out

        m_pct = re.search(r"\[(\d+)%\]", out)
        if m_pct:
            state.volume = int(m_pct.group(1))

        state.is_muted = "[off]" in out.lower()

        if state.is_muted:
            state.status = "MUTED"
        elif state.volume < 40:
            state.status = "LOW_VOLUME"
        else:
            state.status = "OK"
    except Exception as e:
        state.status = "UNAVAILABLE"
        state.details = f"amixer error: {e}"
    return state


def _set_linux_alsa(volume: int | None = None, unmute: bool = True) -> bool:
    """Aplica volumen y unmute con amixer."""
    ok = True
    try:
        if unmute:
            subprocess.run(["amixer", "sset", "Capture", "cap"], capture_output=True, timeout=2)
            subprocess.run(["amixer", "sset", "Capture", "unmute"], capture_output=True, timeout=2)
        if volume is not None:
            vol_pct = max(0, min(100, volume))
            res = subprocess.run(
                ["amixer", "sset", "Capture", f"{vol_pct}%"],
                capture_output=True,
                timeout=2,
            )
            if res.returncode != 0:
                ok = False
    except Exception:
        return False
    return ok


def _get_macos_state() -> MicState:
    """Consulta volumen en macOS vía osascript."""
    state = MicState(backend="macos")
    try:
        res = subprocess.run(
            ["osascript", "-e", "input volume of (get volume settings)"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        out = res.stdout.strip()
        if out.isdigit():
            state.volume = int(out)
            state.is_muted = state.volume == 0
            state.status = "MUTED" if state.is_muted else ("LOW_VOLUME" if state.volume < 40 else "OK")
    except Exception as e:
        state.status = "UNAVAILABLE"
        state.details = str(e)
    return state


def _set_macos(volume: int | None = None, unmute: bool = True) -> bool:
    """Ajusta volumen en macOS vía osascript."""
    try:
        vol = max(1, min(100, volume if volume is not None else 100))
        res = subprocess.run(
            ["osascript", "-e", f"set volume input volume {vol}"],
            capture_output=True,
            timeout=2,
        )
        return res.returncode == 0
    except Exception:
        return False


def _get_windows_state(device_name: str | None = None) -> MicState:
    """Consulta volumen y mute en Windows vía CoreAudio (optimizar_mic)."""
    state = MicState(backend="windows")
    try:
        import optimizar_mic as om

        target = (device_name or "").strip()
        dev = None
        if target and target != "Predeterminado del sistema":
            try:
                dev = om._capture_device_by_sd_name(target)
            except Exception:
                dev = None
        if dev is None:
            dev = om._default_capture_device()
        st = om.get_mic_state(dev)
        if st:
            state.volume = int(st[0])
            state.is_muted = bool(st[1])
            state.status = "MUTED" if state.is_muted else ("LOW_VOLUME" if state.volume < 40 else "OK")
    except Exception as e:
        state.status = "UNAVAILABLE"
        state.details = str(e)
    return state


def _set_windows(volume: int | None = 100, unmute: bool = True, device_name: str | None = None) -> bool:
    """Aplica volumen y boost en Windows vía CoreAudio."""
    try:
        import optimizar_mic as om

        target = (device_name or "").strip()
        dev = None
        if target and target != "Predeterminado del sistema":
            try:
                dev = om._capture_device_by_sd_name(target)
            except Exception:
                dev = None
        if dev is None:
            dev = om._default_capture_device()
        ok_lvl, _ = om.apply_mic_level(dev, volume if volume is not None else 100)
        try:
            om.apply_boost(dev)
        except Exception:
            pass
        return bool(ok_lvl)
    except Exception:
        return False


# ── Funciones de Alto Nivel ──────────────────────────────────────────────────


def get_mic_state(device_name: str | None = None) -> MicState:
    """Obtiene el estado actual del micrófono según el backend detectado."""
    b = detect_backend()
    if b == "pipewire":
        st = _get_linux_pipewire_state()
    elif b == "pulseaudio":
        st = _get_linux_pulseaudio_state()
    elif b == "alsa":
        st = _get_linux_alsa_state()
    elif b == "windows":
        st = _get_windows_state(device_name)
    elif b == "macos":
        st = _get_macos_state()
    else:
        st = MicState(backend="unknown", status="UNAVAILABLE", details="Sistema de audio desconocido")

    if device_name:
        st.device_name = device_name
    return st


def set_mic_volume(volume_pct: int = 100, device_name: str | None = None) -> bool:
    """Ajusta el volumen del micrófono en el sistema operativo (0 - 100%)."""
    b = detect_backend()
    if b == "pipewire":
        return _set_linux_pipewire(volume=volume_pct, unmute=False)
    elif b == "pulseaudio":
        return _set_linux_pulseaudio(volume=volume_pct, unmute=False)
    elif b == "alsa":
        return _set_linux_alsa(volume=volume_pct, unmute=False)
    elif b == "windows":
        return _set_windows(volume=volume_pct, unmute=False, device_name=device_name)
    elif b == "macos":
        return _set_macos(volume=volume_pct, unmute=False)
    return False


def unmute_mic(device_name: str | None = None) -> bool:
    """Desmutea el micrófono en el sistema operativo."""
    b = detect_backend()
    if b == "pipewire":
        return _set_linux_pipewire(volume=None, unmute=True)
    elif b == "pulseaudio":
        return _set_linux_pulseaudio(volume=None, unmute=True)
    elif b == "alsa":
        return _set_linux_alsa(volume=None, unmute=True)
    elif b == "windows":
        return _set_windows(volume=None, unmute=True, device_name=device_name)
    elif b == "macos":
        return _set_macos(volume=None, unmute=True)
    return False


def auto_fix(target_volume: int = 100, device_name: str | None = None) -> dict[str, Any]:
    """Ejecuta una corrección automática completa (desmute y ajuste a nivel óptimo)."""
    backend = detect_backend()
    before = get_mic_state(device_name)
    actions = []

    if before.is_muted:
        unmute_mic(device_name)
        actions.append("Desmuteo del micrófono en el sistema")

    if before.volume < target_volume or before.is_muted:
        set_mic_volume(target_volume, device_name)
        actions.append(f"Ajuste de volumen de captura a {target_volume}%")

    # Si estamos en Windows, intentar boost de CoreAudio
    if backend == "windows":
        try:
            import optimizar_mic as om

            dev = om._default_capture_device()
            ok_boost, msg_boost = om.apply_boost(dev)
            if ok_boost and msg_boost:
                actions.append(msg_boost)
        except Exception:
            pass

    time.sleep(0.1)
    after = get_mic_state(device_name)

    success = (not after.is_muted) and (after.volume >= min(target_volume, 80))
    if not actions:
        actions.append("El micrófono ya se encontraba en estado óptimo (desmuteado y con buen nivel)")

    return {
        "success": success,
        "backend": backend,
        "before_volume": before.volume,
        "before_muted": before.is_muted,
        "after_volume": after.volume,
        "after_muted": after.is_muted,
        "actions": actions,
    }


# ── Compatibilidad de Dispositivos y Frecuencias (ALSA / PortAudio) ─────────


def check_device_compatibility(device: int | str | None = None, target_sr: int = SAMPLE_RATE) -> dict[str, Any]:
    """Comprueba si el dispositivo de audio soporta la frecuencia objetivo.

    En Linux con hardware ALSA (ej. hw:1,0), PortAudio arroja PaErrorCode -9997
    si se pide 16 kHz directo. Esta función identifica si requiere remuestreo nativo.
    """
    if sd is None:
        return {
            "device_id": None,
            "device_name": "No sounddevice",
            "compatible": False,
            "target_sr": target_sr,
            "native_sr": target_sr,
            "needs_resampling": False,
            "error": "sounddevice no disponible",
        }

    dev_id = None
    dev_name = "default"
    try:
        if device is None or device == "":
            dev_id = sd.default.device[0]
        elif isinstance(device, int):
            dev_id = device
        else:
            # Buscar por nombre
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0 and str(device).lower() in d["name"].lower():
                    dev_id = i
                    break

        if dev_id is not None and dev_id >= 0:
            info = sd.query_devices(dev_id)
            dev_name = info["name"]
            default_sr = int(info.get("default_samplerate", 44100))
        else:
            dev_id = None
            default_sr = 44100
    except Exception as e:
        return {
            "device_id": None,
            "device_name": str(device),
            "compatible": False,
            "target_sr": target_sr,
            "native_sr": target_sr,
            "needs_resampling": False,
            "error": str(e),
        }

    # Intentar target_sr directo
    try:
        sd.check_input_settings(device=dev_id, samplerate=target_sr, channels=1)
        return {
            "device_id": dev_id,
            "device_name": dev_name,
            "compatible": True,
            "target_sr": target_sr,
            "native_sr": target_sr,
            "needs_resampling": False,
            "error": None,
        }
    except Exception as err_target:
        # Falla target_sr: probar frecuencias nativas candidatas
        candidates = [default_sr, 48000, 44100, 32000, 22050]
        supported_sr = None
        for cand in candidates:
            try:
                sd.check_input_settings(device=dev_id, samplerate=cand, channels=1)
                supported_sr = cand
                break
            except Exception:
                continue

        if supported_sr:
            return {
                "device_id": dev_id,
                "device_name": dev_name,
                "compatible": False,
                "target_sr": target_sr,
                "native_sr": supported_sr,
                "needs_resampling": True,
                "error": str(err_target),
            }
        else:
            return {
                "device_id": dev_id,
                "device_name": dev_name,
                "compatible": False,
                "target_sr": target_sr,
                "native_sr": default_sr,
                "needs_resampling": False,
                "error": f"Dispositivo no configurable: {err_target}",
            }


# ── Medición Acústica en Vivo ────────────────────────────────────────────────


def measure_signal(
    duration: float = 3.0,
    device: int | str | None = None,
    on_level: Callable[[float], None] | None = None,
    target_sr: int = SAMPLE_RATE,
) -> dict[str, Any]:
    """Captura audio del micrófono y realiza un análisis acústico riguroso.

    Soporta remuestreo automático si el dispositivo de hardware no acepta 16 kHz
    directamente (evitando fallos -9997 de PortAudio).
    """
    if sd is None:
        return {
            "dur": duration,
            "piso": 0.0,
            "p90": 0.0,
            "peak": 0.0,
            "rms": 0.0,
            "snr_db": 0.0,
            "clipping_pct": 0.0,
            "hum_detected": False,
            "verdict": "ERROR: sounddevice no disponible",
            "recommendations": ["Instalar sounddevice y drivers de audio."],
        }

    compat = check_device_compatibility(device, target_sr=target_sr)
    use_sr = compat["native_sr"]
    dev_id = compat["device_id"]
    needs_resample = compat["needs_resampling"]

    buffer: list[np.ndarray] = []

    def callback(indata, frames, time_info, status):
        # Tomar canal 0 si viene en estéreo
        chunk = indata[:, 0].copy() if indata.ndim > 1 else indata.copy().flatten()
        buffer.append(chunk)
        if on_level:
            chunk_rms = float(np.sqrt(np.mean(chunk**2)))
            try:
                on_level(chunk_rms)
            except Exception:
                pass

    try:
        bs = int(use_sr * 0.05)  # bloques de 50 ms
        with sd.InputStream(
            device=dev_id,
            samplerate=use_sr,
            channels=1,
            dtype="float32",
            blocksize=bs,
            callback=callback,
        ):
            sd.sleep(int(duration * 1000))
    except Exception as e:
        return {
            "dur": duration,
            "piso": 0.0,
            "p90": 0.0,
            "peak": 0.0,
            "rms": 0.0,
            "snr_db": 0.0,
            "clipping_pct": 0.0,
            "hum_detected": False,
            "verdict": f"ERROR al abrir micrófono: {e}",
            "veredicto": f"ERROR: {e}",
            "recommendations": [
                f"Error del sistema de captura: {e}",
                "Verifica que ningún otro programa tenga bloqueado el micrófono.",
                "Prueba seleccionando 'Predeterminado del sistema' en Configuración.",
            ],
        }

    if not buffer:
        raw_audio = np.zeros(0, dtype=np.float32)
    else:
        raw_audio = np.concatenate(buffer)

    # Remuestrear a 16 kHz si se capturó a frecuencia nativa diferente
    if needs_resample and len(raw_audio) > 0:
        audio = resample_audio(raw_audio, use_sr, target_sr)
    else:
        audio = raw_audio

    # Análisis de métricas
    n_samples = len(audio)
    if n_samples == 0:
        return {
            "dur": duration,
            "piso": 0.0,
            "p90": 0.0,
            "peak": 0.0,
            "rms": 0.0,
            "snr_db": 0.0,
            "clipping_pct": 0.0,
            "hum_detected": False,
            "verdict": "SILENCIO",
            "veredicto": "SILENCIO",
            "recommendations": ["No se capturaron muestras de audio del dispositivo."],
        }

    # Ventanas de 100 ms para percentiles
    win = int(target_sr * 0.1)
    frames_rms = []
    for i in range(0, n_samples - win + 1, win // 2):
        chunk = audio[i : i + win]
        frames_rms.append(float(np.sqrt(np.mean(chunk**2))))

    if not frames_rms:
        frames_rms = [float(np.sqrt(np.mean(audio**2)))]

    rms_arr = np.array(frames_rms)
    piso = float(np.percentile(rms_arr, 10))
    p90 = float(np.percentile(rms_arr, 90))
    peak = float(np.max(np.abs(audio)))
    rms_global = float(np.sqrt(np.mean(audio**2)))

    # SNR
    snr = 20.0 * math.log10((p90 + 1e-6) / (piso + 1e-6))

    # Clipping
    clip_count = np.sum(np.abs(audio) >= CLIP_THRESHOLD)
    clipping_pct = float((clip_count / n_samples) * 100)

    # Silencio digital
    zero_ratio = float(np.mean(np.abs(audio) < 1e-5))
    is_silence = (p90 < RMS_SILENCE) or (zero_ratio > 0.6)

    # Hum
    has_hum = detect_mains_hum(audio, sr=target_sr)

    # Veredicto y recomendaciones
    recs = []
    if is_silence:
        verdict = "SILENCIO"
        recs.append("El micrófono está en silencio digital o apagado/desenchufado.")
        recs.append("Verifica el botón físico de mute del micrófono o teclado.")
        recs.append("Usa 'Solucionar y Optimizar' para desmutearlo en el sistema operativo.")
    elif clipping_pct > 0.5:
        verdict = "CLIPPING"
        recs.append(f"Se detectó distorsión por saturación ({clipping_pct:.1f}% de clipping).")
        recs.append("Aleja el micrófono de tu boca o reduce ligeramente la ganancia.")
    elif p90 < RMS_VERY_LOW:
        verdict = "VERY_LOW"
        recs.append(f"El nivel de voz es crítico (p90 = {p90:.4f} < {RMS_VERY_LOW}).")
        recs.append("Whisper o Parakeet perderán oraciones completas.")
        recs.append("Ejecuta 'Solucionar y Optimizar' para elevar el volumen del sistema al 100%.")
    elif p90 < RMS_WEAK:
        verdict = "WEAK"
        recs.append(f"El nivel de voz es bajo (p90 = {p90:.4f}).")
        recs.append("Habla más cerca del micrófono o sube el volumen del sistema.")
    elif snr < SNR_MIN_DB and piso > 0.03:
        verdict = "NOISY"
        recs.append(f"Ambiente muy ruidoso (SNR = {snr:.1f} dB, piso = {piso:.3f}).")
        recs.append("El perfil 'Clase Universitaria' o 'Aula Ruidosa' ayudará a filtrar el ruido.")
    else:
        verdict = "OPTIMAL"
        recs.append("El nivel y claridad del micrófono son excelentes para transcripción.")

    if has_hum:
        recs.append("Se detectó zumbido eléctrico (50/60 Hz). Revisa la conexión a tierra o el cargador.")

    veredicto_compat = "OK" if verdict == "OPTIMAL" else verdict
    return {
        "dur": duration,
        "piso": piso,
        "p90": p90,
        "peak": peak,
        "rms": rms_global,
        "snr_db": snr,
        "clipping_pct": clipping_pct,
        "hum_detected": has_hum,
        "is_digital_silence": is_silence,
        "verdict": verdict,
        "veredicto": veredicto_compat,
        "recommendations": recs,
    }


# ── Clase MicTroubleshooter ──────────────────────────────────────────────────


class MicTroubleshooter:
    """Instancia principal para diagnóstico, pruebas y reparación de micrófonos."""

    def __init__(self, device_name: str | None = None, device_id: int | None = None):
        self.device_name = device_name
        self.device_id = device_id
        self.backend = detect_backend()

    def get_state(self) -> MicState:
        return get_mic_state(self.device_name)

    def diagnose(self) -> dict[str, Any]:
        """Ejecuta un diagnóstico completo del estado del sistema y compatibilidad."""
        state = self.get_state()
        compat = check_device_compatibility(self.device_id or self.device_name)
        return {
            "backend": self.backend,
            "volume": state.volume,
            "is_muted": state.is_muted,
            "status": state.status,
            "details": state.details,
            "device_name": compat["device_name"],
            "native_sr": compat["native_sr"],
            "needs_resampling": compat["needs_resampling"],
            "compat_error": compat["error"],
        }

    def auto_fix(self, target_volume: int = 100) -> dict[str, Any]:
        """Corrige mute y volumen bajo."""
        return auto_fix(target_volume=target_volume, device_name=self.device_name)

    def measure(self, duration: float = 3.0, on_level: Callable[[float], None] | None = None) -> dict[str, Any]:
        """Ejecuta la prueba acústica."""
        return measure_signal(
            duration=duration,
            device=self.device_id or self.device_name,
            on_level=on_level,
        )


if __name__ == "__main__":
    print("=== AudioClass Mic Troubleshooter ===")
    print(f"Backend detectado: {detect_backend()}")
    st = get_mic_state()
    print(f"Estado de Micrófono: {st.status} | Volumen: {st.volume}% | Mute: {st.is_muted}")
    if len(sys.argv) > 1 and sys.argv[1] == "--fix":
        print("\nAplicando auto_fix()...")
        res = auto_fix()
        print("Resultado:", res)
    elif len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("\nGrabando prueba de 3 segundos... habla ahora!")
        meas = measure_signal(duration=3.0, on_level=lambda v: print(f"VU: {'#' * int(v * 40)}"))
        print("\nResultado Acústico:")
        for k, v in meas.items():
            print(f"  {k}: {v}")
