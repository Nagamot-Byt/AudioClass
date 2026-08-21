#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sound_error_solver.py — Solucionador automatico de problemas de audio
=====================================================================
Analiza un buffer de audio, detecta problemas comunes y aplica
correcciones automaticas (gain boost, normalizacion, trim de silencio,
eliminacion de clipping). Tambien genera una lista de acciones manuales
que el usuario debe tomar si la correccion automatica no es suficiente.

Flujo tipico en la app:
    fixes, fixed_audio = solve_audio_issues(raw_buffer, report)
    for fix in fixes:
        log(f"{fix.description}: {fix.before_metric:.4f} -> {fix.after_metric:.4f}")
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

from audio_quality_checker import (
    check_audio_quality, AudioQualityReport,
    RMS_SILENCE, RMS_DEBIL, RMS_OK, CLIP_THRESHOLD,
)


@dataclass
class SoundFix:
    """Una correccion aplicada al audio."""
    name: str             # "gain_boost", "clip_normalize", "trim_silence", "denoise"
    description: str      # Descripcion legible por el usuario
    before: float         # Metrica antes de la correccion
    after: float          # Metrica despues de la correccion
    unit: str = ""        # "rms_p90", "peak", "silence_ratio", "snr_db"
    success: bool = True  # Si la correccion se pudo aplicar


def _apply_gain(audio: np.ndarray, target_rms: float = 0.12) -> np.ndarray:
    """Aplica ganancia para llevar el RMS p90 a un nivel objetivo."""
    current_rms = float(np.sqrt(np.mean(audio ** 2)))
    if current_rms < 1e-10:
        return audio  # No se puede boostear silencio
    gain = target_rms / current_rms
    # Limitar gain a un maximo razonable (10x)
    gain = min(gain, 10.0)
    boosted = audio * gain
    # Clip a [-1, 1]
    return np.clip(boosted, -1.0, 1.0)


def _normalize_clipping(audio: np.ndarray) -> np.ndarray:
    """Normaliza el audio para que el pico quede en 0.95 (evita clipping).
    Si el audio ya tiene pico <= 0.95 y > 0.01, se retorna sin cambios."""
    peak = float(np.max(np.abs(audio)))
    if peak < 0.01:
        return audio  # silencio, no normalizar
    if peak <= 0.95:
        return audio  # ya esta en rango seguro
    # Tiene clipping: reducir a 0.95
    target_peak = 0.95
    gain = target_peak / peak
    normalized = audio * gain
    return np.clip(normalized, -1.0, 1.0)


def _trim_silence(audio: np.ndarray, sr: int, threshold: float = RMS_SILENCE,
                  min_silence_sec: float = 0.5) -> np.ndarray:
    """Elimina silencios largos del inicio y final del audio."""
    win = int(sr * 0.05)  # ventanas de 50 ms
    if win < 1:
        return audio

    # Encontrar inicio: primera ventana con RMS > threshold
    start = 0
    for i in range(0, len(audio) - win, win // 2):
        chunk = audio[i:i + win]
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms > threshold:
            start = max(0, i - win)  # margen de seguridad
            break
    else:
        # Todo es silencio
        return audio

    # Encontrar fin: ultima ventana con RMS > threshold
    end = len(audio)
    for i in range(len(audio) - win, start, -(win // 2)):
        chunk = audio[i:i + win]
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        if rms > threshold:
            end = min(len(audio), i + win * 2)
            break

    return audio[start:end]


def _soft_clip(audio: np.ndarray, limit: float = 0.98) -> np.ndarray:
    """Aplica soft clipping para reducir distorsion en picos cercanos a 1.0."""
    mask = np.abs(audio) > limit
    if not np.any(mask):
        return audio
    result = audio.copy()
    over = np.abs(result[mask])
    # Soft compression: x / (1 + |x|) escalado para que llegue al limit
    compressed = np.sign(result[mask]) * (over / (1.0 + over)) * (limit / (limit / (1.0 + limit)))
    result[mask] = compressed
    return np.clip(result, -1.0, 1.0)


def solve_audio_issues(audio: np.ndarray, sr: int = 16000,
                       report: Optional[AudioQualityReport] = None,
                       config: Optional[dict] = None) -> Tuple[List[SoundFix], np.ndarray]:
    """Analiza y corrige automaticamente problemas de audio.

    Args:
        audio: Buffer numpy float32 (flatten, mono).
        sr: Sample rate.
        report: Reporte de calidad previo (si no se pasa, se calcula).
        config: Config de la app (para ajustar ganancia manual del usuario).

    Returns:
        Tupla (fixes_aplicados, audio_corregido).
    """
    if audio is None or len(audio) == 0:
        return [], np.array([], dtype=np.float32)

    audio = np.asarray(audio, dtype=np.float64).flatten()
    original = audio.copy()

    if report is None:
        report = check_audio_quality(audio, sr, config)

    fixes: List[SoundFix] = []

    # -- 1) Clipping: normalizar + soft clip -----------------------------------
    if report.clipping_pct > 0.1:
        peak_before = report.peak
        audio = _normalize_clipping(audio)
        audio = _soft_clip(audio, limit=0.98)
        peak_after = float(np.max(np.abs(audio)))
        new_clip = float(np.sum(np.abs(audio) >= CLIP_THRESHOLD) / len(audio) * 100)
        fixes.append(SoundFix(
            name="clip_normalize",
            description=f"Normalizado y soft-clip aplicado (clipping {report.clipping_pct:.2f}% -> {new_clip:.2f}%)",
            before=peak_before,
            after=peak_after,
            unit="peak",
            success=new_clip < report.clipping_pct,
        ))

    # -- 2) Audio muy debil: boost de ganancia ---------------------------------
    if report.rms_p90 < RMS_DEBIL and report.rms_p90 > RMS_SILENCE:
        gain_before = report.rms_p90
        # Calcular ganancia necesaria para llegar a nivel OK
        target = RMS_OK
        # Si el usuario tiene ganancia manual en config, usarla
        if config and config.get("mic_gain", 1.0) > 1.0:
            target = min(config["mic_gain"] * 0.12, 0.3)  # respetar tope
        audio = _apply_gain(audio, target_rms=target)
        new_rms = float(np.sqrt(np.mean(audio ** 2)))
        # Recalcular p90
        frames = []
        win = int(sr * 0.1)
        for i in range(0, len(audio) - win + 1, win // 2):
            chunk = audio[i:i + win]
            frames.append(float(np.sqrt(np.mean(chunk ** 2))))
        new_p90 = float(np.percentile(frames, 90)) if frames else new_rms
        fixes.append(SoundFix(
            name="gain_boost",
            description=f"Ganancia aplicada (p90 {gain_before:.4f} -> {new_p90:.4f})",
            before=gain_before,
            after=new_p90,
            unit="rms_p90",
            success=new_p90 > gain_before,
        ))

    # -- 3) Clipping post-boost: normalizar de nuevo ---------------------------
    peak_now = float(np.max(np.abs(audio)))
    if peak_now > 0.99:
        audio = _normalize_clipping(audio)
        audio = _soft_clip(audio, limit=0.98)
        peak_after = float(np.max(np.abs(audio)))
        fixes.append(SoundFix(
            name="clip_normalize_post_boost",
            description=f"Re-normalizado post-ganancia (peak {peak_now:.4f} -> {peak_after:.4f})",
            before=peak_now,
            after=peak_after,
            unit="peak",
            success=peak_after <= 0.99,
        ))

    # -- 4) Silencio excesivo: trim del inicio y final -------------------------
    if report.silence_ratio > 0.80 and report.rms_p90 > RMS_SILENCE:
        len_before = len(audio)
        audio = _trim_silence(audio, sr, threshold=RMS_SILENCE, min_silence_sec=0.5)
        len_after = len(audio)
        trimmed_s = (len_before - len_after) / sr
        if trimmed_s > 0.5:
            fixes.append(SoundFix(
                name="trim_silence",
                description=f"Silencio recortado ({trimmed_s:.1f}s eliminados del inicio/final)",
                before=report.silence_ratio,
                after=0.0,
                unit="silence_ratio",
                success=True,
            ))

    # -- 5) Ganancia manual del usuario (si config la tiene) -------------------
    if config and config.get("mic_gain", 1.0) > 1.0:
        user_gain = config["mic_gain"]
        # Aplicar solo si no se ya aplico boost automatico
        already_boosted = any(f.name == "gain_boost" for f in fixes)
        if not already_boosted:
            current_rms = float(np.sqrt(np.mean(audio ** 2)))
            target = current_rms * user_gain
            if target < 0.5:  # no mas de nivel 0.5
                audio = _apply_gain(audio, target_rms=min(target, 0.3))
                new_rms = float(np.sqrt(np.mean(audio ** 2)))
                fixes.append(SoundFix(
                    name="user_gain",
                    description=f"Ganancia manual del usuario (x{user_gain:.1f}) aplicada",
                    before=current_rms,
                    after=new_rms,
                    unit="rms_mean",
                    success=new_rms > current_rms,
                ))

    # -- Convertir a float32 para compatibilidad con el pipeline ---------------
    audio = audio.astype(np.float32)

    return fixes, audio


def suggest_manual_actions(report: AudioQualityReport) -> List[str]:
    """Genera acciones manuales especificas segun los problemas detectados.
    
    Estas acciones son para problemas que NO se pueden corregir automaticamente
    (hardware, permisos, drivers, configuracion de Windows).
    """
    actions = []

    if "silence" in report.issues:
        actions.append("1. Abre Configuracion de Windows > Sistema > Sonido > Entrada")
        actions.append("   y verifica que el medidor de nivel se mueva al hablar.")
        actions.append("2. Verifica que el microfono no este muteado (hardware o software).")
        actions.append("3. Actualiza el driver de audio (Realtek u otro).")
        actions.append("4. En AudioClass: Configuracion > clic 'Auto-detectar microfono'.")

    if "too_quiet" in report.issues:
        actions.append("1. Acerca el microfono a 15-30 cm de tu boca.")
        actions.append("2. En AudioClass: Configuracion > sube la Ganancia a 2.0-3.0x.")
        actions.append("3. Verifica que el nivel de entrada no este en 0 en Windows.")
        actions.append("4. Usa auriculares con microfono integrado para mejor calidad.")

    if "clipping" in report.issues:
        actions.append("1. Alejate del microfono o baja el volumen de entrada.")
        actions.append("2. En Windows: Configuracion > Sonido > Entrada > Propiedades > Nivel.")
        actions.append("3. Si usas auriculares, verifica que el microfono no este tapado.")

    if "noisy" in report.issues:
        actions.append("1. Cierra programas que reproduzcan audio (videos, musica, notificaciones).")
        actions.append("2. Usa auriculares con microfono integrado (mejor aislamiento).")
        actions.append("3. Activa la reduccion de ruido del driver de audio.")
        actions.append("4. Grabar en un lugar silencioso cuando sea posible.")

    if "mostly_silence" in report.issues:
        actions.append("1. Verifica que estes hablando durante toda la grabacion.")
        actions.append("2. El pipeline recortara silencios, pero si no hay voz, el texto sera vacio.")
        actions.append("3. Prueba grabar una prueba corta y revisa el audio mejorado.")

    if "no_voice_frequency" in report.issues:
        actions.append("1. Verifica que el audio contiene voz y no musica o ruido tonal.")
        actions.append("2. Whisper esta optimizado para voz humana (200-4000 Hz).")

    if not actions:
        actions.append("El audio esta en buen estado. No se requieren acciones adicionales.")

    return actions


def format_fix_report(fixes: List[SoundFix]) -> str:
    """Formatea la lista de correcciones aplicadas como texto legible."""
    if not fixes:
        return "No se aplicaron correcciones automaticas."

    lines = ["Correcciones automaticas aplicadas:"]
    for i, fix in enumerate(fixes, 1):
        status = "OK" if fix.success else "PARCIAL"
        lines.append(f"  {i}. [{status}] {fix.description}")
        lines.append(f"     {fix.unit}: {fix.before:.4f} -> {fix.after:.4f}")
    return "\n".join(lines)
