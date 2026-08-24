"""
locales — Sistema de internacionalización (i18n) para AudioClass
"""

from .i18n import get_available_languages, get_language, set_language, t

__all__ = ["get_available_languages", "get_language", "set_language", "t"]
