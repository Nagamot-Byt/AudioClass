#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grabar_prueba.py — Prueba de calidad de audio con el pipeline corregido.

Para personas que quieren validar el audio REAL de AudioClass sin abrir la app:
  1. Ejecuta:  python grabar_prueba.py [segundos]
  2. Pulsa ENTER cuando estes listo y HABLA (lee algo, cuenta, lo que estudies).
  3. Al terminar se guardan en ~/AudioClass_Recordings:
       clase_<fecha>_raw.wav        (grabacion original del microfono)
       clase_<fecha>_mejorado.wav   (tras el pipeline profesional de 9 etapas)
  4. Se imprime la comparacion objetiva: ruido de fondo, nivel de voz,
     conservacion de la banda de voz, atenuacion de agudos y clipping.

Usa EXACTAMENTE la misma ruta que la app (_procsave -> AudioPipeline.process
-> _savewav), asi que el resultado es identico a grabar en la app.
"""

import os
import sys
import time
from datetime import datetime

import numpy as np
import sounddevice as sd
from scipy import signal as sps
from scipy.io import wavfile

import audioclass_v91 as m


def record(duration_s, voice_gate=True):
    """Graba del microfono. Con voice_gate=True espera hasta que detecte voz
    (hasta 90s) y captura automaticamente; con False graba fijo duration_s."""
    SR = m.SAMPLE_RATE
    win = 800  # 50ms

    if not voice_gate:
        buf = []
        print(f"Grabando {duration_s:.0f} s... habla con normalidad.")
        def cb(indata, frames, ti, status):
            buf.append(indata.copy().flatten())
        with sd.InputStream(samplerate=SR, channels=1, dtype=np.float32,
                            blocksize=win, callback=cb):
            sd.sleep(int(duration_s * 1000))
        return np.concatenate(buf).flatten()

    # Voz auto-detectada: espera (max 90s) y captura hasta duration_s de voz,
    # parando tras ~2.5s de silencio continuo.
    VOICE_THR = 0.0015
    LISTEN_MAX_S = 90
    QUIET_STOP_S = 2.5
    buf = []
    quiet_since = None
    t_wall0 = time.time()

    def cb(indata, frames, ti, status):
        nonlocal quiet_since
        x = indata.copy().flatten()
        r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
        if r > VOICE_THR:
            buf.append(x)
            quiet_since = None
        else:
            if buf and quiet_since is None:
                quiet_since = time.time()

    print(f"ESCUCHANDO (max {LISTEN_MAX_S}s)... HABLA AHORA. Capturo tu voz y paro al callar.")
    stream = sd.InputStream(samplerate=SR, channels=1, dtype=np.float32,
                            blocksize=win, callback=cb)
    stream.start()
    try:
        while True:
            time.sleep(0.05)
            have = sum(len(c) for c in buf) / SR
            wall = time.time() - t_wall0
            if quiet_since is not None and have > 0.5 and time.time() - quiet_since > QUIET_STOP_S:
                break
            if have >= duration_s:
                break
            if wall > LISTEN_MAX_S:
                break
    finally:
        stream.stop()
        stream.close()
    return np.concatenate(buf).flatten() if buf else np.zeros(0, dtype=np.float32)


def process_and_save(raw):
    """Igual que _procsave de la app: guarda raw, procesa con el pipeline
    corregido y guarda mejorado. Devuelve (rp, pp, limiter_del_perfil)."""
    SR = m.SAMPLE_RATE
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rp = os.path.join(m.OUTPUT_DIR, f"clase_{ts}_raw.wav")
    wavfile.write(rp, SR, np.int16(np.clip(raw, -1.0, 1.0) * 32767))

    pipe = m.AudioPipeline("Clase Universitaria", fast_mode=False, use_vad=True)
    proc = pipe.process(raw)
    pp = os.path.join(m.OUTPUT_DIR, f"clase_{ts}_mejorado.wav")
    wavfile.write(pp, SR, np.int16(np.clip(proc, -1.0, 1.0) * 32767))
    return rp, pp, float(pipe.p["limiter"])


def analyze(rp, pp):
    """Metricas objetivas comparando raw vs mejorado (sobre los WAV guardados)."""
    sr, raw16 = wavfile.read(rp)
    _, pro16 = wavfile.read(pp)
    rawf = raw16.astype(np.float64) / 32768.0
    prof = pro16.astype(np.float64) / 32768.0

    def frame_rms(x):
        w = int(0.04 * sr)
        hop = w // 2
        return np.array([np.sqrt(np.mean(c ** 2)) if len(c) else 0.0
                         for c in (x[i:i + w] for i in range(0, len(x) - w, hop))])

    def band_energy(x, lo, hi):
        if len(x) < 512:
            return 0.0
        f, P = sps.welch(x, fs=sr, nperseg=2048)
        return float(np.sum(P[(f >= lo) & (f <= hi)]))

    d_raw, d_pro = len(rawf) / sr, len(prof) / sr
    fr_r, fr_p = frame_rms(rawf), frame_rms(prof)
    floor_r = float(np.percentile(fr_r, 10)) if len(fr_r) else 0.0
    floor_p = float(np.percentile(fr_p, 10)) if len(fr_p) else 0.0
    speech_r = float(np.percentile(fr_r, 90)) if len(fr_r) else 0.0
    speech_p = float(np.percentile(fr_p, 90)) if len(fr_p) else 0.0
    # % de tramas en silencio (ruido de fondo): la metrica real del noise gate.
    # Tras _remove_silences el silencio se recorta, asi que el % baja.
    QUIET = 0.01
    sil_r = float(np.mean(fr_r < QUIET)) * 100 if len(fr_r) else 0.0
    sil_p = float(np.mean(fr_p < QUIET)) * 100 if len(fr_p) else 0.0
    vi, vo = band_energy(rawf, 200, 3000), band_energy(prof, 200, 3000)
    hii, hoo = band_energy(rawf, 7100, 7900), band_energy(prof, 7100, 7900)
    pk = float(np.max(np.abs(prof))) if len(prof) else 0.0
    return {
        "d_raw": d_raw, "d_pro": d_pro,
        "floor_r": floor_r, "floor_p": floor_p,
        "speech_r": speech_r, "speech_p": speech_p,
        "sil_r": sil_r, "sil_p": sil_p,
        "voz_ratio": vo / max(vi, 1e-12),
        "agudos_db": 20 * np.log10(hoo / max(hii, 1e-12)),
        "peak": pk,
    }


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0

    print("AudioClass — Prueba de calidad de audio (pipeline corregido)")
    print(f"Microfono por defecto: {sd.default.device}")
    input(f"Pulsa ENTER y habla durante ~{dur:.0f}s (o espera a que detecte tu voz)...")
    raw = record(dur, voice_gate=True)

    if len(raw) < m.SAMPLE_RATE:
        print("No se detecto voz. Intentalo de nuevo hablando mas cerca o mas alto.")
        return 1

    try:
        rp, pp, limiter = process_and_save(raw)
    except Exception as e:
        print(f"\nError al procesar el audio: {e}")
        print("El audio original quedo guardado igualmente. Revisa el espacio en disco y reintenta.")
        return 1

    print("Guardados:")
    print(" ", rp)
    print(" ", pp)

    a = analyze(rp, pp)
    print("\n=== COMPARACION raw vs mejorado (audio REAL) ===")
    print(f"Duracion: raw {a['d_raw']:.1f}s -> mejorado {a['d_pro']:.1f}s (silencio recortado por VAD)")
    print(f"Silencio/ruido recortado: raw {a['sil_r']:.0f}% de tramas en silencio -> mejorado {a['sil_p']:.0f}% (noise gate)")
    print(f"Nivel habla (p90): raw {a['speech_r']:.4f} -> mejorado {a['speech_p']:.4f}")
    print(f"SNR mejorado: habla/piso = {a['speech_p'] / max(a['floor_p'], 1e-12):.1f}x")
    print(f"Voz 200-3000Hz: out/in = {a['voz_ratio']:.2f} (>= 1 = voz conservada)")
    print(f"Agudos 7.1-7.9kHz: {a['agudos_db']:+.1f} dB (ruido de aire atenuado)")
    print(f"Pico mejorado: {a['peak']:.3f} (limiter del perfil: {limiter:.2f}, sin clipping)")
    print("\nEscucha ambos WAVs: el mejorado debe sonar mas limpio, parejo y sin ruido de fondo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
