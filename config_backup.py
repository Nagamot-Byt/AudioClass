"""config_backup.py — Backup y restore de configuracion AudioClass.

Permite exportar la configuracion actual a un archivo JSON con timestamp
e importar desde un backup previo, validando integridad y version.

Uso:
    from config_backup import export_config, import_config, list_backups

    success, msg = export_config()           # backup automatico
    success, msg = import_config("backup.json")  # restaurar
    backups = list_backups()                  # listar backups
"""

import json
import os
import shutil
from datetime import datetime

_BACKUP_DIR = os.path.join(os.path.expanduser("~"), ".audioclass", "backups")


def _ensure_backup_dir():
    os.makedirs(_BACKUP_DIR, exist_ok=True)


def export_config(config_path=None, backup_path=None):
    """Exporta la configuracion actual a un archivo de backup.

    Args:
        config_path: Path del archivo de config a exportar.
            Default: ~/.audioclass/config.json
        backup_path: Path destino del backup. Si es None, genera uno
            automatico con timestamp.

    Returns:
        Tupla (success: bool, message: str)
    """
    try:
        if config_path is None:
            config_path = os.path.join(os.path.expanduser("~"), ".audioclass", "config.json")

        if not os.path.exists(config_path):
            return False, f"Archivo de configuracion no encontrado: {config_path}"

        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        # Envolver con metadata
        backup_data = {
            "_backup_metadata": {
                "version": config.get("_config_version", "unknown"),
                "exported_at": datetime.now().isoformat(),
                "source": config_path,
                "app_version": "9.1.10",
            },
            "config": config,
        }

        if backup_path is None:
            _ensure_backup_dir()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(_BACKUP_DIR, f"audioclass_backup_{timestamp}.json")

        # Asegurar directorio del destino
        os.makedirs(os.path.dirname(os.path.abspath(backup_path)), exist_ok=True)

        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        return True, f"Backup creado: {backup_path}"

    except Exception as e:
        return False, f"Error al crear backup: {e}"


def import_config(backup_path, config_path=None, overwrite=True):
    """Importa configuracion desde un backup.

    Args:
        backup_path: Path del archivo de backup a importar.
        config_path: Path destino de la configuracion.
            Default: ~/.audioclass/config.json
        overwrite: Si True, sobrescribe la config existente.
            Si False, solo importa si la config actual esta vacia o corrupta.

    Returns:
        Tupla (success: bool, message: str)
    """
    try:
        if not os.path.exists(backup_path):
            return False, f"Backup no encontrado: {backup_path}"

        with open(backup_path, encoding="utf-8") as f:
            backup_data = json.load(f)

        # Validar estructura del backup
        if "_backup_metadata" not in backup_data or "config" not in backup_data:
            return False, "Archivo de backup con formato invalido (faltan metadatos)"

        metadata = backup_data["_backup_metadata"]
        config = backup_data["config"]

        # Validar que tiene los campos basicos
        if "local_model" not in config:
            return False, "Backup no contiene configuracion valida (falta local_model)"

        if config_path is None:
            config_path = os.path.join(os.path.expanduser("~"), ".audioclass", "config.json")

        # Verificar si hay config existente
        if os.path.exists(config_path) and not overwrite:
            with open(config_path, encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("local_model"):
                return False, "Ya existe una configuracion valida. Use overwrite=True para reemplazar."

        # Crear backup de la config actual antes de sobrescribir
        if os.path.exists(config_path):
            pre_backup = config_path + f".pre_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(config_path, pre_backup)

        # Escribir la config
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        src_version = metadata.get("version", "unknown")
        exported_at = metadata.get("exported_at", "unknown")
        return True, f"Config importada desde backup (v{src_version}, exportado: {exported_at})"

    except json.JSONDecodeError:
        return False, "Archivo de backup corrupto (JSON invalido)"
    except Exception as e:
        return False, f"Error al importar backup: {e}"


def list_backups():
    """Lista todos los backups disponibles.

    Returns:
        Lista de dicts con info de cada backup:
        [{"path": str, "exported_at": str, "version": str, "size_kb": float}]
    """
    _ensure_backup_dir()
    backups = []
    for fname in sorted(os.listdir(_BACKUP_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(_BACKUP_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("_backup_metadata", {})
            size_kb = os.path.getsize(fpath) / 1024
            backups.append(
                {
                    "path": fpath,
                    "filename": fname,
                    "exported_at": meta.get("exported_at", "unknown"),
                    "version": meta.get("version", "unknown"),
                    "app_version": meta.get("app_version", "unknown"),
                    "size_kb": round(size_kb, 1),
                }
            )
        except Exception:
            continue
    return backups


def cleanup_old_backups(keep=10):
    """Elimina backups antiguos, manteniendo solo los mas recientes.

    Args:
        keep: Numero minimo de backups a conservar.

    Returns:
        Numero de backups eliminados.
    """
    _ensure_backup_dir()
    backups = sorted(
        [f for f in os.listdir(_BACKUP_DIR) if f.endswith(".json")],
        reverse=True,
    )
    removed = 0
    for fname in backups[keep:]:
        try:
            os.remove(os.path.join(_BACKUP_DIR, fname))
            removed += 1
        except Exception:
            pass
    return removed
