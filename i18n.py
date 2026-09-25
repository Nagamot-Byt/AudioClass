#!/usr/bin/env python3
"""
i18n.py — Módulo de internacionalización (i18n) para AudioClass.
===============================================================
Permite cambiar el idioma de la interfaz (ES / EN) de forma dinámica,
cargando los diccionarios desde locales/es.json y locales/en.json.
"""

import json
import os
import sys

_CURRENT_LANG = "es"
_LOCALES = {}


def _get_locales_dir():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
        dir_path = os.path.join(base, "locales")
        if os.path.isdir(dir_path):
            return dir_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")


def load_locales():
    global _LOCALES
    locales_dir = _get_locales_dir()
    for lang in ["es", "en"]:
        file_path = os.path.join(locales_dir, f"{lang}.json")
        if os.path.isfile(file_path):
            try:
                with open(file_path, encoding="utf-8") as f:
                    _LOCALES[lang] = json.load(f)
            except Exception:
                _LOCALES[lang] = {}
        else:
            _LOCALES[lang] = {}


def set_language(lang_code):
    global _CURRENT_LANG
    if lang_code in ["es", "en"]:
        _CURRENT_LANG = lang_code


def get_language():
    return _CURRENT_LANG


def t(key, default=None, **kwargs):
    if not _LOCALES:
        load_locales()
    dict_lang = _LOCALES.get(_CURRENT_LANG, {})
    val = dict_lang.get(key)
    if val is None:
        dict_es = _LOCALES.get("es", {})
        val = dict_es.get(key, default if default is not None else key)
    if kwargs and isinstance(val, str):
        try:
            return val.format(**kwargs)
        except Exception:
            return val
    return val
