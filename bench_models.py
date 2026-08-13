#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench_models.py — Compara tiny/base/small sobre tts_clase.wav.

Usa el MISMO motor de la app (LocalWhisperEngine) con language="auto",
mide el tiempo real y calcula el WER (Word Error Rate) contra el guion
original del TTS. Normaliza acentos/puntuacion y expande digitos a
palabras en espanol ("1972" -> "mil novecientos setenta y dos") para no
castigar a whisper por escribir numeros como digitos.
"""
import re
import sys
import time
import unicodedata

import numpy as np
from scipy.io import wavfile

from audioclass_core import LocalWhisperEngine

WAV = "tts_clase.wav"
GUION_PY = "gen_clase_tts.py"

# ── Extraer el guion de referencia desde gen_clase_tts.py ─────────────────────
def load_reference():
    src = open(GUION_PY, encoding="utf-8").read()
    m = re.search(r'texto = \((.*?)\)', src, re.S)
    parts = re.findall(r'"([^"]*)"', m.group(1))
    return " ".join(parts)

# ── Normalizacion ─────────────────────────────────────────────────────────────
_UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete",
             "ocho", "nueve", "diez", "once", "doce", "trece", "catorce",
             "quince", "dieciseis", "diecisiete", "dieciocho", "diecinueve",
             "veinte"]
_DECENAS = ["", "", "veinti", "treinta", "cuarenta", "cincuenta", "sesenta",
            "setenta", "ochenta", "noventa"]
_CENTENAS = ["", "ciento", "doscientos", "trescientos", "cuatrocientos",
             "quinientos", "seiscientos", "setecientos", "ochocientos",
             "novecientos"]


def _num_under_100(n):
    if n < 21:
        return _UNIDADES[n]
    d, u = divmod(n, 10)
    if d == 2 and 0 < u <= 9:
        return "veinti" + _UNIDADES[u]
    if u == 0:
        return _DECENAS[d]
    return _DECENAS[d] + " y " + _UNIDADES[u]


def _num_under_1000(n):
    if n < 100:
        return _num_under_100(n)
    c, r = divmod(n, 100)
    s = _CENTENAS[c] if c != 1 or r else "cien"
    if r:
        s += " " + _num_under_100(r)
    return s


def _num_under_1000000(n):
    if n < 1000:
        return _num_under_1000(n)
    c, r = divmod(n, 1000)
    if c == 1:
        s = "mil"
    else:
        s = _num_under_1000(c) + " mil"
    if r:
        s += " " + _num_under_1000(r)
    return s


def num_to_words(n):
    if n == 0:
        return "cero"
    if n < 1000000:
        return _num_under_1000000(n)
    m, r = divmod(n, 1000000)
    s = (_num_under_1000(m) if m < 1000 else _num_under_1000000(m)) + " millones"
    if r:
        s += " " + _num_under_1000000(r)
    return s


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def normalize(text):
    t = text.lower()
    t = _strip_accents(t)
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    toks = []
    for tok in t.split():
        if tok.isdigit():
            toks.extend(num_to_words(int(tok)).split())
        else:
            toks.append(tok)
    return toks

# ── WER (Levenshtein a nivel palabra) ─────────────────────────────────────────
def wer(ref, hyp):
    ref, hyp = list(ref), list(hyp)
    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1):
        d[i][0] = i
    for j in range(len(hyp) + 1):
        d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    return d[len(ref)][len(hyp)] / max(len(ref), 1)


def audio_duration(path):
    sr, d = wavfile.read(path)
    return len(d) / sr


def run_model(name):
    eng = LocalWhisperEngine(name, language="auto")
    t0 = time.time()
    res = eng.transcribe(WAV, timestamps=False)
    elapsed = time.time() - t0
    return res, elapsed


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ref = normalize(load_reference())
    dur = audio_duration(WAV)
    print(f"Guion de referencia: {len(ref)} palabras | audio: {dur:.1f}s")

    rows = []
    for name in ("tiny", "base", "small"):
        t0 = time.time()
        res, elapsed = run_model(name)
        total = time.time() - t0  # incluye carga del modelo + transcripcion
        text = res.get("text", "") or ""
        hyp = normalize(text)
        w = wer(ref, hyp)
        rows.append((name, w, elapsed, total, res.get("chunks"), res.get("workers"), text))
        print(f"\n=== {name} | WER {w*100:.1f}% | transcribe {elapsed:.1f}s | "
              f"total {total:.1f}s | chunks {res.get('chunks')} | workers {res.get('workers')} ===")
        print(f"  idioma detectado: {res.get('language')}")
        print(f"  texto ({len(text)} chars): {text[:150]}...")

    print("\n=== RESUMEN ===")
    print(f"{'modelo':<7} {'WER':>6} {'acc':>6} {'transc':>7} {'total':>7} {'x-duracion':>9}")
    for name, w, el, tot, *_ in sorted(rows, key=lambda r: r[1]):
        print(f"{name:<7} {w*100:>5.1f}% {100-w*100:>5.1f}% {el:>6.1f}s {tot:>6.1f}s {el/dur:>8.2f}x")
    best = min(rows, key=lambda r: r[1])
    print(f"\nMejor precision: {best[0]} (WER {best[1]*100:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
