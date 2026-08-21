#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audio_quality_checker.py — Verificador de calidad de audio para transcripcion
==============================================================================
Analiza un buffer de audio (numpy float32) o un archivo WAV y devuelve un
reporte con:
  - Veredicto: OK / WARN / FAIL
  - Metricas: RMS, p90, peak, SNR, clipping, silencio, energia espectral
  - Lista de problemas detectados
  - Sugerencias concretas para mejorar

Uso tipico en la app:
    report = check_audio_quality(raw_buffer)
    if report.verdict == "FAIL":
        mostrar_advertencia(report)
    elif report.verdict == "WARN":
        mostrar_consejo(report)
"""

import os
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Tuple


# -- Umbrales calibrados con optimizar_mic.py y test_mic_detection.py ---------
RMS_SILENCE = 0.005       # p90 < este valor = silencio digital
RMS_DEBIL = 0.03          # p90 < este valor = muy debil para buena transcripcion
RMS_OK = 0.05             # p90 >= este valor = nivel aceptable
RMS_IDEAL = 0.15          # p90 >= este valor = nivel ideal para whisper
CLIP_THRESHOLD = 0.99     # muestras por encima de este valor = clipping
CLIP_WARN_PCT = 0.5       # > 0.5% de samples clipping = problema
SILENCE_RATIO_WARN = 0.70 # > 70% del tiempo en silencio = sospechoso
SNR_MIN_DB = 10.0         # SNR < 10 dB = mucho ruido de fondo
SPEECH_BAND_LOW = 200     # Hz - banda de voz
SPEECH_BAND_HIGH = 4000   # Hz - banda de voz


@dataclass
class AudioQualityReport:
    """Reporte de calidad de audio para transcripcion."""
    verdict: str = "OK"           # "OK" | "WARN" | "FAIL"
    rms_mean: float = 0.0
    rms_p50: float = 0.0
    rms_p90: float = 0.0
    peak: float = 0.0
    snr_db: float = 0.0
    clipping_pct: float = 0.0
    silence_ratio: float = 0.0    # fraccion de tiempo en silencio
    speech_energy: float = 0.0    # energia en banda de voz (0-1 normalizada)
    duration_s: float = 0.0
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    severity: str = "info"        # "info" | "warning" | "error"
    message: str = ""
    auto_fixable: bool = False    # True si el solver puede corregirlo automaticamente


def _rms_frames(audio: np.ndarray, sr: int, win_ms: int = 100) -> np.ndarray:
    """Calcula el RMS por tramas de win_ms milisegundos."""
    win = int(sr * win_ms / 1000)
    if win < 1:
        win = 1
    hop = win // 2
    frames = []
    for i in range(0, len(audio) - win + 1, hop):
        chunk = audio[i:i + win]
        frames.append(float(np.sqrt(np.mean(chunk ** 2))))
    return np.array(frames, dtype=np.float64) if frames else np.array([0.0])


def _spectral_energy(audio: np.ndarray, sr: int,
                     f_low: int = SPEECH_BAND_LOW,
                     f_high: int = SPEECH_BAND_HIGH) -> float:
    """Fraccion de energia espectral en la banda de voz (0-1)."""
    n = len(audio)
    if n < sr * 0.1:  # menos de 100 ms
        return 0.0
    # FFT rapida (potencia de 2 para velocidad)
    fft_size = 1
    while fft_size < n:
        fft_size *= 2
    fft_size = min(fft_size, n)
    seg = audio[:fft_size]
    spectrum = np.abs(np.fft.rfft(seg * np.hanning(fft_size)))
    freqs = np.fft.rfftfreq(fft_size, d=1.0 / sr)
    total_energy = np.sum(spectrum ** 2)
    if total_energy < 1e-20:
        return 0.0
    speech_mask = (freqs >= f_low) & (freqs <= f_high)
    speech_energy = np.sum(spectrum[speech_mask] ** 2)
    return float(speech_energy / total_energy)


def _estimate_snr(audio: np.ndarray, sr: int) -> float:
    """Estima SNR en dB usando percentiles del RMS.
    
    Usa percentil 10 como piso de ruido y percentil 90 como nivel de senal,
    que es mas robusto con senales periodicas (voz, musica) que el promedio
    de los mas bajos/altos."""
    frames = _rms_frames(audio, sr, win_ms=100)
    if len(frames) < 4:
        return 0.0
    sorted_f = np.sort(frames)
    # Piso de ruido: percentil 10 (mas robusto que promedio de los mas bajos)
    noise_floor = float(np.percentile(sorted_f, 10))
    # Senal: percentil 90 (nivel de habla real)
    speech_ref = float(np.percentile(sorted_f, 90))
    if noise_floor < 1e-10:
        return 60.0  # sin ruido detectable
    snr = speech_ref / noise_floor
    return float(20.0 * np.log10(max(snr, 1e-10)))


def check_audio_quality(audio: np.ndarray, sr: int = 16000,
                        config: Optional[dict] = None) -> AudioQualityReport:
    """Analiza la calidad de un buffer de audio y devuelve un reporte.

    Args:
        audio: Buffer numpy float32 (flatten, mono).
        sr: Sample rate (default 16000).
        config: Config de la app (opcional, para ajustar umbrales).

    Returns:
        AudioQualityReport con veredicto, metricas, problemas y sugerencias.
    """
    report = AudioQualityReport()

    if audio is None or len(audio) == 0:
        report.verdict = "FAIL"
        report.severity = "error"
        report.message = "Audio vacio: no hay datos para analizar."
        report.issues.append("empty")
        report.suggestions.append("Graba una clase de al menos 5 segundos.")
        return report

    audio = np.asarray(audio, dtype=np.float64).flatten()
    report.duration_s = len(audio) / sr

    if report.duration_s < 1.0:
        report.verdict = "FAIL"
        report.severity = "error"
        report.message = f"Audio muy corto ({report.duration_s:.1f}s). Se necesitan al menos 2 segundos."
        report.issues.append("too_short")
        report.suggestions.append("Graba una clase de al menos 5 segundos.")
        return report

    # -- Metricas base ---------------------------------------------------------
    report.rms_mean = float(np.sqrt(np.mean(audio ** 2)))
    frames = _rms_frames(audio, sr, win_ms=100)
    report.rms_p50 = float(np.median(frames))
    report.rms_p90 = float(np.percentile(frames, 90))
    report.peak = float(np.max(np.abs(audio)))

    # -- Clipping --------------------------------------------------------------
    clip_count = int(np.sum(np.abs(audio) >= CLIP_THRESHOLD))
    report.clipping_pct = (clip_count / len(audio)) * 100.0

    # -- Silencio --------------------------------------------------------------
    silence_frames = int(np.sum(frames < RMS_SILENCE))
    report.silence_ratio = silence_frames / max(len(frames), 1)

    # -- SNR -------------------------------------------------------------------
    report.snr_db = _estimate_snr(audio, sr)

    # -- Energia espectral -----------------------------------------------------
    report.speech_energy = _spectral_energy(audio, sr)

    # -- Deteccion de problemas ------------------------------------------------
    issues = []
    suggestions = []
    auto_fixable = False

    # 1) Audio completamente silencioso
    if report.rms_p90 < RMS_SILENCE:
        issues.append("silence")
        suggestions.append("El audio esta en silencio. Verifica que el microfono no este muteado.")
        suggestions.append("Revisa: Configuracion > Sistema > Sonido > Entrada.")
        suggestions.append("Abre Configuracion > Auto-detectar micrófono.")

    # 2) Audio muy debil (p90 < 0.03)
    elif report.rms_p90 < RMS_DEBIL:
        issues.append("too_quiet")
        suggestions.append(f"Nivel bajo (p90={report.rms_p90:.4f}). La transcripcion puede omitir palabras.")
        suggestions.append("Acercate al microfono o sube la ganancia (Configuracion > Ganancia).")
        suggestions.append("Usa 'Auto-detectar' para encontrar el mejor microfono disponible.")
        auto_fixable = True  # el solver puede aplicar boost de ganancia

    # 3) Clipping excesivo
    if report.clipping_pct > CLIP_WARN_PCT:
        issues.append("clipping")
        suggestions.append(f"Recorte detectado ({report.clipping_pct:.1f}% de muestras al limite).")
        suggestions.append("Baja el volumen de entrada o alejate del microfono.")
        auto_fixable = True  # el solver puede normalizar

    # 4) Mucho ruido de fondo
    if report.snr_db < SNR_MIN_DB and report.rms_p90 >= RMS_SILENCE:
        issues.append("noisy")
        suggestions.append(f"Ruido de fondo alto (SNR={report.snr_db:.1f} dB). La transcripcion puede ser imprecisa.")
        suggestions.append("Cierra programas con audio (videos, musica). Usa auriculares con microfono.")
        suggestions.append("Activa el reduccion de ruido en Configuracion.")

    # 5) Silencio excesivo (>70% del tiempo)
    if report.silence_ratio > SILENCE_RATIO_WARN and report.rms_p90 >= RMS_SILENCE:
        issues.append("mostly_silence")
        suggestions.append(f"El audio tiene {report.silence_ratio*100:.0f}% de silencio. Puede haber muy poca voz.")
        suggestions.append("Verifica que estes hablando durante la grabacion.")
        suggestions.append("El pipeline de audio recortara el silencio, pero el texto puede ser muy corto.")

    # 6) Energia espectral muy baja en banda de voz
    if report.speech_energy < 0.05 and report.rms_p90 >= RMS_SILENCE:
        issues.append("no_voice_frequency")
        suggestions.append("La energia en la banda de voz (200-4000 Hz) es muy baja.")
        suggestions.append("Puede haber musica o ruido tonal en vez de voz. Verifica que estes grabando voz.")

    # -- Determinar veredicto ---------------------------------------------------
    if report.rms_p90 < RMS_SILENCE:
        report.verdict = "FAIL"
        report.severity = "error"
        report.message = (
            f"Audio insuficiente para transcribir (p90={report.rms_p90:.4f}, "
            f"{20*np.log10(max(report.rms_p90,1e-6)):.0f} dB). "
            "La transcripcion saldra vacia o con basura."
        )
    elif len(issues) >= 2 or report.rms_p90 < RMS_DEBIL:
        report.verdict = "WARN"
        report.severity = "warning"
        report.message = (
            f"Calidad cuestionable para transcribir (p90={report.rms_p90:.4f}, "
            f"SNR={report.snr_db:.1f} dB). Se recomienda mejorar antes de transcribir."
        )
    elif issues:
        report.verdict = "WARN"
        report.severity = "warning"
        report.message = f"Advertencia: {', '.join(issues)}. La transcripcion puede no ser optima."
    else:
        report.verdict = "OK"
        report.severity = "info"
        report.message = f"Audio en buen estado (p90={report.rms_p90:.4f}, SNR={report.snr_db:.1f} dB)."

    report.issues = issues
    report.suggestions = suggestions
    report.auto_fixable = auto_fixable

    return report


def check_wav_file(path: str, sr: int = 16000,
                   config: Optional[dict] = None) -> AudioQualityReport:
    """Analiza un archivo WAV y devuelve el reporte de calidad."""
    try:
        from scipy.io import wavfile
        sr_file, data = wavfile.read(path)
        if data.dtype == np.int16:
            data = data.astype(np.float64) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float64) / 2147483648.0
        else:
            data = data.astype(np.float64)
        if data.ndim > 1:
            data = data[:, 0]  # mono
        return check_audio_quality(data, sr=sr_file, config=config)
    except Exception as e:
        report = AudioQualityReport()
        report.verdict = "FAIL"
        report.severity = "error"
        report.message = f"No se pudo leer el archivo: {e}"
        report.issues.append("read_error")
        return report


def format_report_text(report: AudioQualityReport) -> str:
    """Formatea el reporte como texto legible para el usuario."""
    lines = []
    lines.append(f"[{report.verdict}] {report.message}")

    if report.duration_s > 0:
        lines.append(f"  Duracion: {report.duration_s:.1f}s")
    lines.append(f"  RMS p90: {report.rms_p90:.4f} ({20*np.log10(max(report.rms_p90,1e-6)):.0f} dB)")
    lines.append(f"  Pico: {report.peak:.4f}")
    lines.append(f"  SNR: {report.snr_db:.1f} dB")
    if report.clipping_pct > 0:
        lines.append(f"  Clipping: {report.clipping_pct:.2f}%")
    lines.append(f"  Silencio: {report.silence_ratio*100:.0f}% del tiempo")

    if report.issues:
        lines.append(f"  Problemas: {', '.join(report.issues)}")
    if report.suggestions:
        lines.append("  Sugerencias:")
        for s in report.suggestions:
            lines.append(f"    - {s}")

    return "\n".join(lines)
