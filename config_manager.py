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
    "colab_key": "",
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
    "theme": "auto",  # dark, light, auto (sigue el tema del sistema)
    "language": "es",  # es, en, pt
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
    # Ganancia del microfono: 1.0 = sin boost, 2.0-5.0 para mics debiles.
    "mic_gain": 1.0,
}

# Versión del schema de configuración. Se incrementa cuando se añaden,
# renombran o eliminan claves. El migrador aplica transforms secuenciales
# de la versión del disco a la versión actual.
CONFIG_VERSION = 5


# ── Migración de configuración entre versiones ───────────────────────────
# Cada migración es una función que transforma un dict in-place de la
# versión N a la versión N+1. Se aplican en orden secuencial.

def _migrate_v1_to_v2(cfg: dict) -> dict:
    """Migración v1 -> v2: renombrar 'colab_key' trivial a vacío.

    En v1 el default de 'colab_key' era 'audioclass' (trivial). En v2
    se cambia a vacío para que el servidor rechace keys débiles.
    Si el usuario tenía 'audioclass', se resetea a vacío.
    """
    trivial_keys = {"audioclass", "admin", "password", "1234", "test"}
    if cfg.get("colab_key", "") in trivial_keys:
        cfg["colab_key"] = ""
    return cfg


def _migrate_v2_to_v3(cfg: dict) -> dict:
    """Migración v2 -> v3: normalizar nombres de modelos Gemini.

    Gemini 1.5 fue retirado en 2025. Si el usuario tenía 'gemini-pro'
    o 'gemini-flash' (nombres viejos), se mapea a los IDs actuales.
    También se normaliza 'gemini_model' a los aliases soportados.
    """
    OLD_MODEL_MAP = {
        "gemini-1.5-flash": "flash",
        "gemini-1.5-pro": "pro",
        "gemini-pro": "pro",
        "gemini-flash": "flash",
        "gemini-1.0-pro": "pro",
        "gemini-1.0-flash": "flash",
    }
    gemini_model = cfg.get("gemini_model", "flash")
    if gemini_model in OLD_MODEL_MAP:
        cfg["gemini_model"] = OLD_MODEL_MAP[gemini_model]
    # Also check full model IDs that users might have set manually
    FULL_ID_MAP = {
        "gemini-1.5-flash": "flash",
        "gemini-1.5-pro": "pro",
        "gemini-2.0-flash": "flash",
        "gemini-2.5-pro": "pro",
    }
    if gemini_model in FULL_ID_MAP:
        cfg["gemini_model"] = FULL_ID_MAP[gemini_model]
    return cfg


def _migrate_v3_to_v4(cfg: dict) -> dict:
    """Migración v3 -> v4: renombrar 'cloud_model' a 'colab_model'.

    El campo 'cloud_model' era ambiguo (¿Gemini cloud? ¿Colab?).
    Se renombra a 'colab_model' para que sea explícito. Si el usuario
    tenía un valor personalizado en 'cloud_model', se copia a 'colab_model'.
    """
    if "cloud_model" in cfg and "colab_model" not in cfg:
        cfg["colab_model"] = cfg["cloud_model"]
    # Eliminar el campo viejo para no confundir
    cfg.pop("cloud_model", None)
    return cfg


def _migrate_v4_to_v5(cfg: dict) -> dict:
    """Migración v4 -> v5: normalizar valores de tema.

    Algunos usuarios escribieron 'Dark', 'LIGHT', 'dark ' (con espacio),
    42 (número), o None. Se normaliza a 'dark', 'light' o 'auto' (lowercase,
    sin espacios). Valores no-string o irreconocibles → fallback a 'auto'.

    Si 'theme' no existe en la config, no lo añade: el paso de defaults
    (DEFAULT_CONFIG) se encargará.
    """
    if "theme" not in cfg:
        return cfg
    theme = cfg["theme"]
    if isinstance(theme, str):
        normalized = theme.strip().lower()
        if normalized in ("dark", "light", "auto"):
            cfg["theme"] = normalized
        else:
            cfg["theme"] = "auto"
    else:
        # None, int, bool, etc.: fallback a auto (sigue el tema del sistema)
        cfg["theme"] = "auto"
    return cfg


# Registro de migraciones: lista de (desde_version, hasta_version, función)
# Se aplican en orden secuencial; cada una transforma vN -> vN+1.
_MIGRATIONS = [
    (1, 2, _migrate_v1_to_v2),
    (2, 3, _migrate_v2_to_v3),
    (3, 4, _migrate_v3_to_v4),
    (4, 5, _migrate_v4_to_v5),
]


def _migrate_config(cfg: dict) -> dict:
    """Aplica todas las migraciones necesarias para llevar la config
    a la versión actual. Devuelve el dict migrado.

    Si la config no tiene versión (configs antiguas), asume v1.
    """
    current_ver = cfg.get("_config_version", 1)
    if current_ver >= CONFIG_VERSION:
        return cfg  # Ya está actualizada

    for from_ver, to_ver, migrate_fn in _MIGRATIONS:
        if current_ver < to_ver and from_ver >= current_ver:
            try:
                cfg = migrate_fn(cfg)
            except Exception:
                pass  # No fallar la app por un error de migración

    cfg["_config_version"] = CONFIG_VERSION
    return cfg


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
    """Carga la configuracion desde JSON. Aplica defaults para claves faltantes,
    descifra secretos y ejecuta migraciones entre versiones. Si el archivo
    no existe, devuelve DEFAULT_CONFIG."""
    cfg_path = path or CONFIG_PATH
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            # Aplicar migraciones de versión
            cfg = _migrate_config(cfg)
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
