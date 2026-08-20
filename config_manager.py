#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_manager.py — Gestion de configuracion persistente de AudioClass
======================================================================
Extraido de audioclass_v91.py para mejorar la mantenibilidad.
Maneja carga/guardado de config, cifrado de secretos (DPAPI/b64) y defaults.
"""

import os
import json
import base64


# ── Rutas por defecto ─────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "AudioClass_Recordings")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(OUTPUT_DIR, "audioclass_config.json")


# ── Configuracion por defecto ─────────────────────────────────────────────
DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "colab_url": "",
    "colab_key": "audioclass",
    "google_creds_path": "",
    "audio_profile": "Clase Universitaria",
    "transcription_mode": "local",
    "local_model": "base",
    # Idioma de whisper: "auto" = detecta el idioma del audio; si no, un
    # codigo ISO (es, en, pt, fr, ...) que se fuerza.
    "whisper_language": "auto",
    "cloud_model": "large-v3",
    "gemini_model": "flash",
    "adapt_provider": "gemini",
    "openai_api_key": "",
    "openai_model": "mini",
    "modo_facil": False,
    "modo_guiado": True,
    "auto_adaptar": False,
    "adaptacion_default": "Analisis Academico Profundo",
    "theme": "dark",
    "vu_sensitivity": 0.25,
    # Microfono elegido por el usuario (por NOMBRE, para sobrevivir a
    # reordenamientos de ids de PortAudio). Vacio = predeterminado del sistema.
    "mic_device": "",
    "first_run": True,
    # Privacidad: el analisis con IA ENVIA el texto de la transcripcion a
    # servidores de Google/OpenAI. Sin consentimiento explicito (ia_consent),
    # la app pide permiso antes del primer uso y nunca envia nada.
    "ia_consent": False,
    "rec_consent_ack": False,
}


# ── Cifrado de secretos (DPAPI en Windows) ────────────────────────────────
_SECRET_FIELDS = ("gemini_api_key", "openai_api_key", "colab_key")


def _encrypt_secret(secret):
    """Cifra un secreto. Devuelve string con prefijo 'dpapi:' o 'b64:'."""
    if not secret:
        return ""
    s = str(secret)
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]

            def _blob(data):
                buf = ctypes.create_string_buffer(data)
                return DATA_BLOB(
                    len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
                )

            crypt32 = ctypes.windll.crypt32
            crypt32.CryptProtectData.argtypes = [
                ctypes.POINTER(DATA_BLOB),
                wintypes.LPCWSTR,
                ctypes.POINTER(DATA_BLOB),
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(DATA_BLOB),
            ]
            crypt32.CryptProtectData.restype = wintypes.BOOL
            try:
                from ctypes import byref

                inb = _blob(s.encode("utf-8"))
                outb = DATA_BLOB()
                if crypt32.CryptProtectData(
                    byref(inb), "audioclass", None, None, None, 0, byref(outb)
                ):
                    raw = ctypes.string_at(outb.pbData, outb.cbData)
                    ctypes.windll.kernel32.LocalFree(outb.pbData)
                    return "dpapi:" + base64.b64encode(raw).decode("ascii")
            except Exception:
                pass
        except Exception:
            pass
    return "b64:" + base64.b64encode(s.encode("utf-8")).decode("ascii")


def _decrypt_secret(value):
    """Descifra un secreto cifrado con _encrypt_secret. Valores legados en
    texto plano se devuelven tal cual (y luego se re-guardan cifrados)."""
    if not value:
        return ""
    v = str(value)
    if v.startswith("b64:"):
        try:
            return base64.b64decode(v[4:]).decode("utf-8")
        except Exception:
            return ""
    if v.startswith("dpapi:") and os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char)),
                ]

            crypt32 = ctypes.windll.crypt32
            crypt32.CryptUnprotectData.argtypes = [
                ctypes.POINTER(DATA_BLOB),
                ctypes.POINTER(wintypes.LPCWSTR),
                ctypes.POINTER(DATA_BLOB),
                ctypes.c_void_p,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(DATA_BLOB),
            ]
            crypt32.CryptUnprotectData.restype = wintypes.BOOL
            try:
                from ctypes import byref

                raw = base64.b64decode(v[6:])
                buf = ctypes.create_string_buffer(raw)
                inb = DATA_BLOB(
                    len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))
                )
                outb = DATA_BLOB()
                if crypt32.CryptUnprotectData(
                    byref(inb), None, None, None, None, 0, byref(outb)
                ):
                    out = ctypes.string_at(outb.pbData, outb.cbData).decode("utf-8")
                    ctypes.windll.kernel32.LocalFree(outb.pbData)
                    return out
            except Exception:
                return ""
        except Exception:
            return ""
    return v


# ── Carga / Guardado ──────────────────────────────────────────────────────
def load_config(path=None):
    """Carga la configuracion desde JSON. Aplica defaults para claves faltantes
    y descifra secretos. Si el archivo no existe, devuelve DEFAULT_CONFIG."""
    cfg_path = path or CONFIG_PATH
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            for k in _SECRET_FIELDS:
                if k in cfg and cfg[k]:
                    cfg[k] = _decrypt_secret(cfg[k])
            return cfg
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(cfg, path=None):
    """Guarda la configuracion a JSON, cifrando los campos secretos."""
    cfg_path = path or CONFIG_PATH
    to_save = dict(cfg)
    for k in _SECRET_FIELDS:
        if k in to_save and to_save[k]:
            to_save[k] = _encrypt_secret(to_save[k])
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2, ensure_ascii=False)
