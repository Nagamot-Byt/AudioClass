#!/usr/bin/env python3
"""mic_optimizer_ui.py — Re-export de la logica de microfono.

La implementacion de MicTestMixin (ahora MicService) vive en
services/mic_service.py para separar la responsabilidad de microfono del
god-object App. Este modulo solo re-exporta para no romper los importadores
existentes (audioclass_v91, etc.).
"""

from services.mic_service import MicTestMixin
