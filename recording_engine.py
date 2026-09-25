#!/usr/bin/env python3
"""recording_engine.py — Re-export de la logica de grabacion.

La implementacion de RecordingMixin (ahora RecordingService) vive en
services/recording_service.py para separar la responsabilidad de grabacion
del god-object App. Este modulo re-exporta todo el API publico anterior
(RecordingMixin, mic_device_id_for, CHANNELS, SAMPLE_RATE) para no romper
los importadores existentes (audioclass_v91, tests).
"""

from services.recording_service import *  # noqa: F403
