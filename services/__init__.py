"""services — Servicios desacoplados de la interfaz (App queda como coordinador).

Cada servicio encapsula una responsabilidad que antes vivía acoplada a la
clase god-object App en audioclass_v91.py: motores de transcripción, grabación,
micrófono, actualizaciones y gestión de modelos. App los instancia y delega,
en lugar de heredar toda la lógica.
"""

from services.mic_service import MicService
from services.model_manager import ModelManager, get_default_model_manager
from services.recording_service import RecordingService
from services.transcription_service import TranscriptionService
from services.update_service import UpdateService

__all__ = [
    "MicService",
    "ModelManager",
    "RecordingService",
    "TranscriptionService",
    "UpdateService",
    "get_default_model_manager",
]
