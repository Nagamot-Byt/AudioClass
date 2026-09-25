#!/usr/bin/env python3
"""update_dialog_ui.py — Re-export de la logica de actualizaciones.

La implementacion de UpdateDialogMixin (ahora UpdateService) vive en
services/update_service.py para separar la responsabilidad de actualizaciones
del god-object App. Este modulo solo re-exporta para no romper los
importadores existentes (audioclass_v91, etc.).
"""

from services.update_service import UpdateDialogMixin
