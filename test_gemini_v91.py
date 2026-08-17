#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AudioClass v9.1 — Verificador de Gemini 2.5 (sin abrir la GUI)
==============================================================
Prueba tu API Key y el flujo completo de "Análisis Académico Profundo"
con gemini-2.0-flash (flash) / gemini-2.5-pro (pro) usando el código real de
audioclass_v91.py (GeminiAdaptationEngine).

USO:
    python test_gemini_v91.py                      # usa la key guardada en Configuracion
    python test_gemini_v91.py --key "AIza..."      # o pasala directamente
    python test_gemini_v91.py --model pro          # probar con Gemini 2.5 Pro
    python test_gemini_v91.py --long               # ademas, probar segmentacion de texto largo
    python test_gemini_v91.py --audio clase.wav    # ademas, probar transcripcion local Whisper
    python test_gemini_v91.py --audio clase.wav --whisper-model small

Requiere: requests (para Gemini). Para --audio: openai-whisper + numpy + scipy.

Salida: [OK] = paso OK, [X] = paso fallido, = advertencia. Al final, un resumen.
"""

import argparse
import json
import os
import re
import sys

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║   AudioClass v9.1 — Verificador de Gemini 2.5                     ║
║   Prueba la API Key y el Analisis Academico Profundo sin la GUI   ║
╚══════════════════════════════════════════════════════════════════╝
"""

SAMPLE_CLASE = (
    "Hoy vamos a estudiar la farmacologia de la amoxicilina. La dosis habitual en adultos es "
    "de 500 mg cada 8 horas. La amoxicilina es un antibiotico betalactamico que inhibe la "
    "sintesis de la pared celular bacteriana. Recordemos que el 15 de marzo de 2023 se "
    "actualizo la guia de tratamiento de la neumonia adquirida en la comunidad. La "
    "presentacion mas comun es la capsula de 500 miligramos y el tratamiento suele durar "
    "entre 7 y 10 dias. En pacientes con alergia a penicilinas esta contraindicada. "
    "Si hay alguna duda, revisen el capitulo 12 del manual."
)

SECCIONES = ["resumen ejecutivo", "tesis", "pilar", "evidencia", "implicaci", "filtrado"]


def obtener_key(arg_key):
    """Key desde: argumento > variable de entorno > config de la app."""
    if arg_key and arg_key.strip():
        return arg_key.strip()
    env = os.environ.get("GEMINI_API_KEY", "").strip()
    if env:
        return env
    cfg = os.path.join(os.path.expanduser("~"), "AudioClass_Recordings", "audioclass_config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                return (json.load(f).get("gemini_api_key") or "").strip()
        except Exception:
            pass
    return ""


def cargar_motor_gemini():
    """Carga GeminiAdaptationEngine real desde audioclass_v91.py.

    Primero intenta importar el modulo completo (si las dependencias de la app
    estan instaladas). Si no, extrae solo la clase y la ejecuta (solo necesita requests).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "audioclass_v91.py")
    if not os.path.exists(path):
        print(f"[X] No se encontro {path}")
        sys.exit(1)

    # Intento 1: import real del modulo (maxima fidelidad)
    try:
        sys.path.insert(0, here)
        import audioclass_v91
        return audioclass_v91.GeminiAdaptationEngine, "modulo completo de la app"
    except Exception as e:
        print(f"No se pudo importar audioclass_v91.py ({e})")
        print("  Uso el motor Gemini extraido directamente del archivo (solo necesita requests).")

    # Intento 2: extraer solo la clase (evita numpy/scipy/sounddevice/customtkinter)
    try:
        with open(path, "r", encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"class GeminiAdaptationEngine:\n", src)
        if not m:
            raise ValueError("clase no encontrada en el archivo")
        start = m.start()
        nxt = src.find("\nclass ", start + 10)
        class_src = src[start:nxt if nxt != -1 else len(src)]
        ns = {}
        exec(compile(class_src, "audioclass_v91.py", "exec"), ns)
        return ns["GeminiAdaptationEngine"], "clase extraida"
    except Exception as e:
        print(f"[X] No se pudo cargar GeminiAdaptationEngine: {e}")
        sys.exit(1)


def probar_key(engine, key, model):
    print("\n── Paso 1: Prueba de la API Key ──────────────────────────────")
    e = engine(key, model)
    print(f"  Modelo a usar: {e._model_name()}")
    ok, msg = e.test_key()
    if ok:
        print(f"  [OK] {msg}")
    else:
        print(f"  [X] {msg}")
    return ok


def probar_adaptacion_corta(engine, key, model):
    print("\n── Paso 2: Analisis Academico Profundo (texto corto) ───────────")
    e = engine(key, model)
    res = e.adapt(SAMPLE_CLASE, "Análisis Académico Profundo")
    if "error" in res:
        print(f"  [X] Error: {res['error']}")
        return False
    text = res.get("text", "")
    if not text:
        print("  [X] Gemini devolvio un texto vacio")
        return False
    low = text.lower()
    encontradas = [s for s in SECCIONES if s in low]
    print(f"  [OK] Respuesta recibida ({len(text)} caracteres)")
    print(f"    Secciones detectadas en la salida: {len(encontradas)}/{len(SECCIONES)}")
    if len(encontradas) < 2:
        print("  La salida no parece seguir el formato academico. Primeros 400 caracteres:")
        print("    " + text[:400].replace("\n", "\n    "))
    else:
        preview = text[:600].replace("\n", "\n    ")
        print("  Vista previa (600 caracteres):")
        print("    " + preview)
    return True


def probar_segmentacion(engine, key, model):
    print("\n── Paso 3: Segmentacion anti-caidas (texto largo >12.000 chars) ──")
    # Repetir el texto hasta superar 12.000 caracteres (umbral del Analisis Academico)
    largo = SAMPLE_CLASE
    while len(largo) < 12500:
        largo += " " + SAMPLE_CLASE
    print(f"  Tamano del texto de prueba: {len(largo):,} caracteres")
    e = engine(key, model)
    res = e.adapt(largo, "Análisis Académico Profundo")
    if "error" in res:
        print(f"  [X] Error: {res['error']}")
        return False
    text = res.get("text", "")
    if not text:
        print("  [X] Gemini devolvio texto vacio en la sintesis final")
        return False
    print(f"  [OK] Analisis final sintetizado ({len(text)} caracteres)")
    return True


def probar_transcripcion_local(audio_path, whisper_model):
    print("\n── Paso 4: Transcripcion local Whisper ─────────────────────────")
    if not audio_path or not os.path.exists(audio_path):
        print(f"  [X] Archivo de audio no encontrado: {audio_path}")
        return False
    try:
        import numpy as np
        from scipy.io import wavfile
    except ImportError:
        print("  [X] Faltan numpy/scipy: pip install numpy scipy")
        return False
    try:
        import whisper
    except ImportError:
        print("  [X] Falta openai-whisper: pip install openai-whisper")
        return False
    try:
        print(f"  Cargando Whisper {whisper_model} (la primera vez lo descarga)...")
        model = whisper.load_model(whisper_model)
        sr, data = wavfile.read(audio_path)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        else:
            data = data.astype(np.float32)
        print(f"  Audio: {len(data) / sr:.1f} s a {sr} Hz")
        result = model.transcribe(
            audio_path,
            language="es",
            task="transcribe",
            fp16=False,
            verbose=False,
            condition_on_previous_text=True,
            initial_prompt=(
                "Esta es una transcripcion de una clase universitaria o conferencia academica en espanol. "
                "El orador principal es el docente o conferencista. "
                "Ignora murmullos de fondo, interrupciones breves y preguntas sin respuesta del docente. "
                "Preserva datos duros: numeros, fechas, dosis, nomenclaturas tecnicas y definiciones literales exactas. "
                "Transcribe fielmente solo lo dicho por el orador principal."
            ),
        )
        text = (result.get("text") or "").strip()
        if not text:
            print("  [X] Whisper devolvio texto vacio")
            return False
        print(f"  [OK] Transcripcion lista ({len(text)} caracteres)")
        print("  Vista previa:")
        print("    " + text[:400].replace("\n", "\n    "))
        return True
    except Exception as e:
        print(f"  [X] Error de transcripcion: {e}")
        return False


def main():
    # Consolas Windows (cp1252) no soportan ╔ [OK] [!]: forzar UTF-8 o reemplazo
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    print(BANNER)
    ap = argparse.ArgumentParser(description="Verificador de Gemini 2.5 de AudioClass v9.1")
    ap.add_argument("--key", default="", help="API Key de Google AI Studio")
    ap.add_argument("--model", default="flash", choices=["flash", "pro"], help="flash | pro (por defecto flash)")
    ap.add_argument("--long", action="store_true", help="Probar segmentacion de texto largo")
    ap.add_argument("--audio", default="", help="Ruta a un .wav para probar transcripcion local")
    ap.add_argument("--whisper-model", default="tiny", help="tiny|base|small (por defecto tiny)")
    args = ap.parse_args()

    try:
        import requests
    except ImportError:
        print("[X] Falta el paquete requests: ejecuta primero  pip install -r requirements_v91.txt")
        sys.exit(1)

    key = obtener_key(args.key)
    if len(key) < 10:
        print("[X] No se encontro una API Key valida.")
        print("  Opciones:")
        print("    1) python test_gemini_v91.py --key \"TU_CLAVE\"")
        print("    2) Abre la app (Configuracion) y guarda tu key en aistudio.google.com/app/apikey")
        print("    3) Variable de entorno GEMINI_API_KEY")
        sys.exit(1)

    print(f"[OK] API Key encontrada ({len(key)} caracteres, terminada en ...{key[-4:]})")
    engine, fuente = cargar_motor_gemini()
    print(f"[OK] Motor Gemini cargado ({fuente})")

    resultados = []
    resultados.append(probar_key(engine, key, args.model))
    resultados.append(probar_adaptacion_corta(engine, key, args.model))
    if args.long:
        resultados.append(probar_segmentacion(engine, key, args.model))
    if args.audio:
        resultados.append(probar_transcripcion_local(args.audio, args.whisper_model))

    print("\n" + "═" * 62)
    ok = all(resultados)
    if ok:
        print("  TODOS LOS PASOS COMPLETADOS — Gemini 2.5 listo en AudioClass v9.1")
        print("     Ya puedes usar la app: graba, transcribe y pulsa 'Analisis Academico Profundo'.")
    else:
        print("  [X] HAY PASOS FALLIDOS — revisa los mensajes de arriba.")
        print("    Si es un error de API Key/permisos, resuelvelo y vuelve a ejecutar este script.")
    print("═" * 62)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
