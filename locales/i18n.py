#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n.py — Motor de internacionalización para AudioClass
======================================================

Soporta múltiples idiomas con fallback a inglés.
Los archivos de traducción están en locales/<lang>.json.

Uso:
    from locales import t, set_language, get_language

    # Obtener traducción
    print(t("app.title"))  # "AudioClass - Grabador de Clases"

    # Cambiar idioma
    set_language("en")

    # Obtener idioma actual
    print(get_language())  # "es"
"""
import json
import os
from pathlib import Path
from typing import Optional

# ── Estado global ────────────────────────────────────────────────────────────
_current_language = "es"  # Idioma por defecto
_translations = {}        # Cache de traducciones cargadas
_fallback = {}            # Traducciones en inglés (fallback)

LOCALES_DIR = Path(__file__).parent
AVAILABLE_LANGUAGES = {
    "es": "Español",
    "en": "English",
    "pt": "Português",
}


def _load_translations(lang: str) -> dict:
    """Carga las traducciones de un idioma desde el archivo JSON."""
    if lang in _translations:
        return _translations[lang]

    filepath = LOCALES_DIR / f"{lang}.json"
    if not filepath.exists():
        return {}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        _translations[lang] = data
        return data
    except Exception:
        return {}


def _flatten_dict(d: dict, prefix: str = "") -> dict:
    """Aplana un diccionario anidado en claves puntuadas.

    Ejemplo:
        {"app": {"title": "AudioClass"}} → {"app.title": "AudioClass"}
    """
    result = {}
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_dict(value, full_key))
        else:
            result[full_key] = value
    return result


def set_language(lang: str):
    """Cambia el idioma actual.

    Args:
        lang: Código de idioma ('es', 'en', 'pt').
    """
    global _current_language, _fallback

    if lang not in AVAILABLE_LANGUAGES:
        lang = "es"  # Fallback a español

    _current_language = lang

    # Cargar fallback en inglés si no es el idioma actual
    if lang != "en":
        _fallback = _flatten_dict(_load_translations("en"))
    else:
        _fallback = {}


def get_language() -> str:
    """Retorna el código del idioma actual."""
    return _current_language


def get_available_languages() -> dict:
    """Retorna diccionario de idiomas disponibles {código: nombre}."""
    return dict(AVAILABLE_LANGUAGES)


def t(key: str, **kwargs) -> str:
    """Traduce una clave al idioma actual.

    Args:
        key: Clave de traducción puntuada (ej: 'app.title', 'wizard.step1').
        **kwargs: Variables para interpolación (ej: t("greeting", name="Juan")).

    Returns:
        Texto traducido. Si no encuentra la traducción, retorna la clave.

    Ejemplos:
        >>> t("app.title")
        'AudioClass - Grabador de Clases'
        >>> t("wizard.welcome", version="9.1")
        'Bienvenido a AudioClass v9.1'
    """
    # Buscar en el idioma actual
    translations = _flatten_dict(_load_translations(_current_language))
    value = translations.get(key)

    # Fallback a inglés si no existe
    if value is None and _fallback:
        value = _fallback.get(key)

    # Si aún no existe, retornar la clave
    if value is None:
        return key

    # Interpolación de variables
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError):
            return value

    return value


def load_language_from_config(config: dict):
    """Carga el idioma desde la configuración de AudioClass.

    Args:
        config: Dict de configuración de AudioClass.
    """
    lang = config.get("language", "es")
    set_language(lang)
