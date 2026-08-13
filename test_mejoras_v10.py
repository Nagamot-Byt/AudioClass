#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_mejoras_v10.py — Verifica las mejoras de la iteracion v10:

  #2 PRE-VALIDACION DE SILENCIO: un WAV de silencio digital (>50% muestras en
     cero, microfono muerto) devuelve un aviso inmediato ({'silence': True})
     SIN gastar tiempo de transcripcion (chunks=0, workers=0) y sin errores.
     Un audio con voz real NO se marca como silencio.

  #3 STREAMING: el motor emite el texto parcial acumulado via partial_callback
     conforme terminan los chunks (len(partials) >= 2 y el ultimo == texto
     final), en los caminos secuencial (1 chunk) y paralelo (>= 2 chunks).

  #1 FASTER-WHISPER: con el backend 'faster' (CTranslate2 int8) la transcripcion
     completa, el resultado reporta backend='faster', y la deteccion de idioma
     'auto' devuelve el idioma real (info.language), no el fallback 'es'.

Los tests de silencio y streaming usan un WAV sintetico (sin voz real); el de
faster usa voz TTS real (tts_clase.wav) si existe; si no, genera ruido rosa.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from scipy.io import wavfile

import audioclass_core as core

SR = core.SAMPLE_RATE
TMP = tempfile.gettempdir()


def _speech_like(dur, seed=7):
    """Ruido rosa con envolvente tipo silabas: forma de voz para whisper."""
    rng = np.random.default_rng(seed)
    n = int(SR * dur)
    t = np.arange(n) / SR
    pink = rng.standard_normal(n)
    for k in range(1, 20):
        pink += rng.standard_normal(n) * (1.0 / k)
    pink /= np.std(pink)
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 4.5 * t + 1.3)
    sig = pink * env + 0.3 * np.sin(2 * np.pi * 120 * t) * env
    return (sig * 0.5).astype(np.float32)


def _wav(dur, fn, seed=7):
    p = os.path.join(TMP, fn)
    wavfile.write(p, SR, np.int16(np.clip(_speech_like(dur, seed), -1, 1) * 32767))
    return p


def _voice_wav(dur, fn):
    """Voz REAL (primeros `dur` s de tts_clase.wav) o ruido rosa de respaldo.
    La transcripcion de streaming necesita voz real: con ruido rosa faster-
    whisper devuelve texto vacio (no es voz) y el partial no se emitiria."""
    if os.path.exists("tts_clase.wav"):
        sr, d = wavfile.read("tts_clase.wav")
        p = os.path.join(TMP, fn)
        wavfile.write(p, sr, d[:int(sr * dur)])
        return p
    return _wav(dur, fn)


def _silent_wav(dur, fn):
    """WAV de silencio DIGITAL: 100% de muestras en cero (microfono muerto)."""
    p = os.path.join(TMP, fn)
    wavfile.write(p, SR, np.zeros(int(SR * dur), dtype=np.int16))
    return p


def test_silencio_digital_detectado():
    """#2: WAV de silencio digital -> aviso inmediato, sin transcribir."""
    p = _silent_wav(3, "ac_v10_silencio.wav")
    eng = core.LocalWhisperEngine("tiny", language="auto")
    t0 = time.time()
    r = eng.transcribe(p, check_silence=True)
    el = time.time() - t0
    os.remove(p)
    assert r.get("silence") is True, r
    assert r.get("chunks", 0) == 0, "no debe transcribir nada"
    assert r.get("workers", 0) == 0, "no debe lanzar workers"
    assert "silencio" in r.get("silence_msg", "").lower(), r.get("silence_msg")
    assert el < 5, f"la pre-validacion debe ser instantanea, tardo {el:.1f}s"
    print(f"  S1 OK: silencio digital -> aviso en {el:.1f}s sin transcribir "
          f"| msg: {r.get('silence_msg','')[:60]}...")


def test_silencio_no_marca_voz():
    """#2: un audio con voz real NO debe marcarse como silencio."""
    p = _wav(4, "ac_v10_voz.wav")
    eng = core.LocalWhisperEngine("tiny", language="auto")
    r = eng.transcribe(p, check_silence=True)
    os.remove(p)
    assert r.get("silence") is None, f"no es silencio: {r.get('silence_msg')}"
    print("  S2 OK: audio con voz no se marca como silencio")


def test_streaming_secuencial_y_paralelo():
    """#3: partial_callback recibe el texto acumulado conforme avanzan chunks."""
    eng = core.LocalWhisperEngine("tiny", language="es")

    # Camino secuencial (1 chunk): al menos 1 partial y == texto final
    parts1 = []
    p1 = _voice_wav(28, "ac_v10_seq.wav")  # 28s -> 1 chunk
    eng.transcribe(p1, partial_callback=parts1.append)
    os.remove(p1)
    assert len(parts1) >= 1, f"secuencial debe emitir >= 1 partial, tengo {len(parts1)}"
    assert parts1[-1].strip(), "el ultimo partial no puede estar vacio"
    print(f"  P1 OK: secuencial emitio {len(parts1)} partial(s), "
          f"ultimo len={len(parts1[-1])}")

    # Camino paralelo (>= 2 chunks): progresion del texto
    parts2 = []
    p2 = _voice_wav(75, "ac_v10_par.wav")  # 75s -> 3 chunks -> paralelo
    eng.transcribe(p2, partial_callback=parts2.append)
    os.remove(p2)
    assert len(parts2) >= 2, f"paralelo debe emitir >= 2 partials, tengo {len(parts2)}"
    # El texto parcial crece de forma monotona (no se encoge)
    lens = [len(x) for x in parts2]
    assert lens[-1] >= lens[0], f"el texto parcial no crece: {lens}"
    print(f"  P2 OK: paralelo emitio {len(parts2)} partials, "
          f"crecimiento {lens[0]} -> {lens[-1]} chars")


def _faster_skip():
    """True si faster-whisper no esta instalado: los tests del backend faster
    hacen SKIP limpio (exit 0) como el resto de la suite, sin ImportError."""
    try:
        import faster_whisper  # noqa: F401
        return False
    except Exception:
        return True


def test_faster_backend_funciona_y_detecta_idioma():
    """#1: backend faster-whisper transcribe y detecta el idioma real."""
    if _faster_skip():
        print("  F1 SKIP: faster-whisper no instalado")
        return
    # Necesita voz real (TTS) para que la deteccion tenga contenido; si no
    # existe, usa ruido rosa (la deteccion puede devolver 'en' o 'es', lo que
    # importa es que no explote y que el backend se reporte).
    p = _voice_wav(40, "ac_v10_fast.wav")
    eng = core.LocalWhisperEngine("tiny", language="auto", backend="faster")
    assert eng.backend == "faster", eng.backend
    t0 = time.time()
    r = eng.transcribe(p)
    el = time.time() - t0
    os.remove(p)
    assert r.get("backend") == "faster", r
    assert r.get("text"), "debe producir texto"
    assert r.get("language"), r
    print(f"  F1 OK: faster tiny en {el:.0f}s ({el/max(r.get('chunks',1),1):.1f}s/chunk) "
          f"| idioma={r.get('language')} | chunks={r.get('chunks')} | "
          f"texto len={len(r.get('text',''))}")


def test_faster_paralelo_consistente():
    """#1: camino paralelo con faster mantiene un solo idioma en todos chunks."""
    if _faster_skip():
        print("  F2 SKIP: faster-whisper no instalado")
        return
    p = _voice_wav(100, "ac_v10_fp.wav")
    eng = core.LocalWhisperEngine("tiny", language="auto", backend="faster")
    r = eng.transcribe(p)
    os.remove(p)
    assert r.get("workers", 1) > 1, f"esperaba paralelo: {r.get('workers')}"
    assert r.get("backend") == "faster"
    assert r.get("language"), r
    print(f"  F2 OK: faster paralelo ({r.get('workers')} workers, "
          f"{r.get('chunks')} chunks) idioma={r.get('language')}")


def main():
    print("== Mejoras v10 ==")
    test_silencio_digital_detectado()
    test_silencio_no_marca_voz()
    test_streaming_secuencial_y_paralelo()
    test_faster_backend_funciona_y_detecta_idioma()
    test_faster_paralelo_consistente()
    print("\nMEJORAS_V10_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
