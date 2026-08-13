#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_clase_tts.py — Genera un WAV de ~70s de voz TTS real en espanol.

PowerShell + System.Speech (sincrono, SetOutputToWaveFile) escribe directamente
el WAV 16-bit mono 22050Hz; luego se convierte a 16kHz mono con scipy para
dejarlo exactamente como lo procesaria la app.
"""
import os
import subprocess
import sys
import tempfile


def main():
    if sys.platform != "win32":
        print("SKIP: solo Windows")
        return 1
    out = os.path.abspath("tts_clase.wav")

    # Texto academico en espanol (~70s a velocidad normal)
    texto = (
        "Bienvenidos a la clase de biologia celular. "
        "Hoy vamos a estudiar la estructura y funcion de la membrana plasmatica. "
        "La membrana esta formada por una bicapa lipidica con proteinas embebidas. "
        "Los fosfolipidos tienen una cabeza hidrofilica y dos colas hidrofobicas. "
        "Esta organizacion permite la separacion del medio intracelular del extracelular. "
        "Las proteinas de membrana cumplen funciones de transporte, señalizacion y adhesion. "
        "Las proteinas de canal permiten el paso de iones como sodio, potasio y calcio. "
        "La bomba de sodio y potasio mantiene el gradiente electroquimico de la celula. "
        "Este proceso requiere energia en forma de ATP. "
        "Ademas, la membrana contiene colesterol que le proporciona fluidez y estabilidad. "
        "Los carbohidratos unidos a proteinas forman glicoproteinas en la superficie externa. "
        "Estas estructuras participan en el reconocimiento celular y la respuesta inmune. "
        "El modelo actual se conoce como el modelo de mosaico fluido. "
        "Fue propuesto por Singer y Nicolson en mil novecientos setenta y dos. "
        "Segun este modelo, las proteinas pueden moverse lateralmente dentro de la bicapa. "
        "La fluidez depende de la temperatura y de la cantidad de acidos grasos insaturados. "
        "A mayor temperatura, mayor movimiento de los fosfolipidos. "
        "Los acidos grasos insaturados tienen dobles enlaces que impiden el empaquetamiento. "
        "Por eso las membranas con mas insaturados son mas fluidas a bajas temperaturas. "
        "Las proteinas perifericas se asocian debilmente con la superficie de la membrana. "
        "En cambio, las proteinas integrales atraviesan completamente la bicapa lipidica. "
        "Las microvellosidades aumentan la superficie de absorcion en el intestino. "
        "La endocitosis permite la entrada de particulas grandes mediante vesiculas. "
        "La exocitosis libera sustancias al exterior de la celula. "
        "Estos procesos son fundamentales para la comunicacion celular. "
        "En resumen, la membrana plasmatica es una estructura dinamica y selectiva. "
        "Su estudio es esencial para comprender la fisiologia celular. "
        "Esto concluye la clase de hoy. Muchas gracias por su atencion."
    )

    ps = f'''
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female,
                          [System.Speech.Synthesis.VoiceAge]::Adult, 0,
                          [System.Globalization.CultureInfo]::GetCultureInfo("es-ES"))
}} catch {{}}
$s.Rate = 0
$s.SetOutputToWaveFile("{out.replace(chr(92), chr(92)*2)}")
$s.Speak(@"
{texto}
"@)
$s.Dispose()
Write-Output "TTS_OK"
'''
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=180,
                       encoding="utf-8", errors="replace")
    print(r.stdout[-500:])
    if r.returncode != 0:
        print("stderr:", r.stderr[-500:])
        return 1
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        print("ERROR: WAV vacio o no creado")
        return 1

    # Convertir a 16kHz mono (igual que la app lo procesaria)
    import numpy as np
    from scipy.io import wavfile
    sr, d = wavfile.read(out)
    if d.ndim > 1:
        d = np.mean(d, axis=1)
    target = 16000
    if sr != target:
        from scipy import signal
        x = d.astype(np.float64) / (32768.0 if d.dtype == np.int16 else 1.0)
        x = signal.resample(x, int(len(x) * target / sr)).astype(np.float32)
        wavfile.write(out, target, np.int16(np.clip(x, -1, 1) * 32767))
        sr = target
    print(f"OK: {out} | {os.path.getsize(out)} bytes | {sr} Hz | "
          f"{os.path.getsize(out) / (sr * 2):.1f}s aprox")
    return 0


if __name__ == "__main__":
    sys.exit(main())
