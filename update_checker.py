#!/usr/bin/env python3
"""
update_checker.py — Sistema de actualización de AudioClass
==========================================================

Funciones:
  - check_for_updates(): Verifica si hay nueva versión en GitHub
  - find_download_asset(): Encuentra el archivo correcto para descargar
  - download_update(): Descarga la actualización con progreso
  - verify_download(): Verifica SHA-256 del archivo descargado
  - install_update(): Reemplaza la instalación actual
  - restart_app(): Reinicia la aplicación

Uso:
    from update_checker import check_for_updates, download_update
    result = check_for_updates("9.1.0")
    if result["update_available"]:
        download_update(result["assets"], callback=progress_callback)
"""

import hashlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import requests

REPO = "Nagamot-Byt/AudioClass"
GITHUB_API = f"https://api.github.com/repos/{REPO}/releases/latest"
SO = platform.system()  # 'Windows', 'Darwin', 'Linux'


def _parse_version(version_str: str) -> tuple:
    """Convierte una cadena de versión a tupla numérica para comparación.

    Soporta formatos como '9.1.0', '9.1', 'v9.1.0', '9.1 Académica'.

    Examples:
        >>> _parse_version("9.1.0")
        (9, 1, 0)
        >>> _parse_version("v9.1")
        (9, 1)
        >>> _parse_version("9.1 Académica")
        (9, 1)
    """
    match = re.search(r"(\d+(?:\.\d+)*)", str(version_str))
    if not match:
        return (0,)
    parts = match.group(1).split(".")
    return tuple(int(p) for p in parts)


def check_for_updates(current_version: str, timeout: int = 10) -> dict:
    """Consulta GitHub para ver si hay una versión más reciente.

    Args:
        current_version: Versión actual (ej: '9.1.0', '9.1 Académica').
        timeout: Timeout de la petición HTTP en segundos.

    Returns:
        dict con:
            - update_available (bool): True si hay una versión más nueva.
            - latest_version (str): Versión más reciente en GitHub.
            - current_version (str): Versión que se pasó como parámetro.
            - release_url (str): URL de la release en GitHub.
            - release_notes (str): Notas de la release.
            - assets (list): Lista de assets disponibles para descargar.
            - sha256_url (str): URL del archivo SHA-256 (si existe).
            - error (str|None): Mensaje de error si falló la consulta.
    """
    result = {
        "update_available": False,
        "latest_version": "",
        "current_version": current_version,
        "release_url": "",
        "release_notes": "",
        "assets": [],
        "sha256_url": "",
        "error": None,
    }

    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        r = requests.get(GITHUB_API, headers=headers, timeout=timeout)

        if r.status_code == 404:
            return result

        if r.status_code != 200:
            result["error"] = f"HTTP {r.status_code}"
            return result

        data = r.json()
        tag = data.get("tag_name", "")
        latest = tag.lstrip("v") if tag else ""

        if not latest:
            result["error"] = "No se pudo obtener la versión"
            return result

        result["latest_version"] = latest
        result["release_url"] = data.get("html_url", "")
        result["release_notes"] = data.get("body", "")[:2000]  # Limitar longitud

        # Recopilar assets
        for asset in data.get("assets", []):
            result["assets"].append(
                {
                    "name": asset.get("name", ""),
                    "url": asset.get("browser_download_url", ""),
                    "size": asset.get("size", 0),
                }
            )

        # Buscar archivo SHA-256
        for asset in data.get("assets", []):
            name = asset.get("name", "")
            if name.endswith(".sha256") or name.endswith(".sha256sum"):
                result["sha256_url"] = asset.get("browser_download_url", "")
                break

        current = _parse_version(current_version)
        latest_parsed = _parse_version(latest)

        if latest_parsed > current:
            result["update_available"] = True

    except requests.exceptions.Timeout:
        result["error"] = "Tiempo de espera agotado"
    except requests.exceptions.ConnectionError:
        result["error"] = "Sin conexión a internet"
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def find_download_asset(assets: list[dict]) -> dict | None:
    """Encuentra el asset correcto para descargar según la plataforma.

    Args:
        assets: Lista de assets de la release.

    Returns:
        dict con 'name', 'url', 'size' o None si no se encontró.
    """
    # Patrones de nombre por plataforma
    patterns = {
        "Windows": [
            r"AudioClass.*\.zip$",  # ZIP con exe
            r"AudioClass.*\.exe$",  # EXE directo
            r"COMPLETA.*\.zip$",  # ZIP completo
        ],
        "Darwin": [
            r"MACOS.*\.dmg$",  # DMG (mejor experiencia)
            r"MACOS.*APP.*\.zip$",  # ZIP con .app bundle
            r"MACOS.*\.zip$",  # ZIP con ejecutable
        ],
        "Linux": [
            r"LINUX.*\.AppImage$",  # AppImage (mejor experiencia)
            r"LINUX.*\.tar\.xz$",  # Tar.xz
            r"LINUX.*part_0*$",  # Primera parte de split
        ],
    }

    platform_patterns = patterns.get(SO, patterns["Linux"])

    for pattern in platform_patterns:
        for asset in assets:
            name = asset.get("name", "")
            if re.search(pattern, name, re.IGNORECASE):
                return asset

    # Fallback: buscar cualquier asset que contenga el nombre del SO
    so_names = {"Windows": "WINDOWS", "Darwin": "MACOS", "Linux": "LINUX"}
    so_name = so_names.get(SO, "LINUX")

    for asset in assets:
        name = asset.get("name", "")
        if so_name in name.upper():
            return asset

    return None


def download_update(
    asset: dict,
    dest_dir: str = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    timeout: int = 300,
) -> tuple[str | None, str | None]:
    """Descarga la actualización desde GitHub.

    Args:
        asset: Dict con 'name', 'url', 'size'.
        dest_dir: Directorio destino (temporal por defecto).
        on_progress: Callback(bytes_downloaded, total_bytes, status_msg).
        timeout: Timeout de la descarga en segundos.

    Returns:
        Tuple (file_path, error_message). file_path es None si falló.
    """
    url = asset.get("url", "")
    name = asset.get("name", "update")
    total_size = asset.get("size", 0)

    if not url:
        return None, "URL de descarga no disponible"

    if dest_dir is None:
        dest_dir = tempfile.mkdtemp(prefix="audioclass_update_")

    dest_path = os.path.join(dest_dir, name)

    try:
        if on_progress:
            on_progress(0, total_size, f"Descargando {name}...")

        # Descargar con streaming
        headers = {"Accept": "application/octet-stream"}
        r = requests.get(url, headers=headers, timeout=timeout, stream=True)

        if r.status_code != 200:
            return None, f"Error HTTP {r.status_code} al descargar"

        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(
                            downloaded, total_size, f"Descargado {downloaded // 1024}KB / {total_size // 1024}KB"
                        )

        if on_progress:
            on_progress(total_size, total_size, "Descarga completada")

        return dest_path, None

    except requests.exceptions.Timeout:
        return None, "Tiempo de espera agotado"
    except requests.exceptions.ConnectionError:
        return None, "Conexión perdida durante la descarga"
    except Exception as e:
        return None, f"Error: {str(e)[:100]}"


def verify_download(
    file_path: str,
    sha256_url: str = None,
    expected_sha256: str = None,
) -> tuple[bool, str]:
    """Verifica la integridad del archivo descargado con SHA-256.

    Args:
        file_path: Ruta al archivo descargado.
        sha256_url: URL del archivo .sha256 en GitHub (opcional).
        expected_sha256: Hash SHA-256 esperado (opcional, alternativo a sha256_url).

    Returns:
        Tuple (is_valid, message).
    """
    if not os.path.exists(file_path):
        return False, "Archivo no encontrado"

    # Calcular SHA-256 del archivo descargado
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    computed = sha256_hash.hexdigest()

    # Si se proporcionó un hash esperado, comparar directamente
    if expected_sha256:
        expected = expected_sha256.strip().lower()
        if computed == expected:
            return True, f"SHA-256 verificado: {computed[:16]}..."
        else:
            return False, f"SHA-256 no coincide: esperado {expected[:16]}..., obtenido {computed[:16]}..."

    # Si se proporcionó una URL de .sha256, descargarla y comparar
    if sha256_url:
        try:
            r = requests.get(sha256_url, timeout=10)
            if r.status_code == 200:
                # Formato típico: "hash  filename" o solo "hash"
                content = r.text.strip().split()[0]
                if computed == content:
                    return True, f"SHA-256 verificado: {computed[:16]}..."
                else:
                    return False, "SHA-256 no coincide con el publicado"
        except Exception:
            pass

    # Sin verificación posible: advertir pero permitir
    return True, f"SHA-256 calculado: {computed[:16]}... (sin referencia para verificar)"


def install_update(
    downloaded_path: str,
    app_dir: str = None,
    on_progress: Callable[[str, str], None] | None = None,
) -> tuple[bool, str]:
    """Instala la actualización reemplazando la instalación actual.

    Args:
        downloaded_path: Ruta al archivo descargado (.zip, .exe, .AppImage, etc).
        app_dir: Directorio de la instalación actual (auto-detectado por defecto).
        on_progress: Callback(status_msg, detail_msg).

    Returns:
        Tuple (success, message).
    """
    if app_dir is None:
        app_dir = str(Path(__file__).parent.resolve())

    try:
        if on_progress:
            on_progress("Preparando instalación...", "")

        # Crear backup de la instalación actual
        backup_dir = os.path.join(app_dir, ".update_backup")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)

        # Respaldar archivos críticos
        critical_files = [
            "audioclass_v91.py",
            "audioclass_core.py",
            "config_manager.py",
            "config_dialog.py",
            "mic_optimizer_ui.py",
            "ai_providers.py",
            "update_checker.py",
            "ui_builder.py",
            "theme.py",
            "recording_engine.py",
            "transcription_engines.py",
            "export_utils.py",
            "audio_quality_checker.py",
            "sound_error_solver.py",
        ]
        for f in critical_files:
            src = os.path.join(app_dir, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(backup_dir, f))

        if on_progress:
            on_progress("Backup creado", f"Respaldado en {backup_dir}")

        # Extraer según tipo de archivo
        file_ext = os.path.splitext(downloaded_path)[1].lower()

        if file_ext == ".zip":
            _install_from_zip(downloaded_path, app_dir, on_progress)
        elif file_ext == ".exe":
            _install_from_exe(downloaded_path, app_dir, on_progress)
        elif downloaded_path.endswith(".tar.xz"):
            _install_from_tarxz(downloaded_path, app_dir, on_progress)
        elif downloaded_path.endswith(".AppImage"):
            _install_from_appimage(downloaded_path, app_dir, on_progress)
        else:
            return False, f"Tipo de archivo no soportado: {file_ext}"

        if on_progress:
            on_progress("¡Instalación completada!", "Reinicia AudioClass para usar la nueva versión")

        return True, "Instalación completada"

    except Exception as e:
        # Restaurar backup en caso de error
        try:
            if os.path.exists(backup_dir):
                for f in os.listdir(backup_dir):
                    src = os.path.join(backup_dir, f)
                    dst = os.path.join(app_dir, f)
                    if os.path.isfile(src):
                        shutil.copy2(src, dst)
        except Exception:
            pass

        return False, f"Error durante la instalación: {str(e)[:100]}"


def _install_from_zip(zip_path: str, app_dir: str, on_progress: Callable | None = None):
    """Extrae un ZIP sobre la instalación actual."""
    import zipfile

    if on_progress:
        on_progress("Extrayendo archivos...", "")

    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            # Evitar path traversal
            member_path = os.path.join(app_dir, member)
            if not os.path.abspath(member_path).startswith(os.path.abspath(app_dir)):
                continue
            z.extract(member, app_dir)

    if on_progress:
        on_progress("Archivos extraídos", "")


def _install_from_exe(exe_path: str, app_dir: str, on_progress: Callable | None = None):
    """Reemplaza el ejecutable actual."""
    if on_progress:
        on_progress("Reemplazando ejecutable...", "")

    # En Windows, el exe actual está en uso. Usamos un truco:
    # renombrar el actual → .old, copiar el nuevo, eliminar .old al reiniciar
    if SO == "Windows":
        current_exe = os.path.join(app_dir, "AudioClass.exe")
        if os.path.exists(current_exe):
            old_exe = current_exe + ".old"
            if os.path.exists(old_exe):
                os.remove(old_exe)
            os.rename(current_exe, old_exe)
            # Programar eliminación al reiniciar
            try:
                subprocess.run(
                    ["cmd", "/c", "timeout", "/t", "3", "/f", "&&", "del", old_exe], capture_output=True, timeout=10
                )
            except Exception:
                pass
        shutil.copy2(exe_path, current_exe)
    else:
        # Linux/macOS: el ejecutable se puede reemplazar directamente
        current_exe = os.path.join(app_dir, "AudioClass")
        shutil.copy2(exe_path, current_exe)
        os.chmod(current_exe, 0o755)


def _install_from_tarxz(tar_path: str, app_dir: str, on_progress: Callable | None = None):
    """Extrae un tar.xz sobre la instalación actual."""
    import tarfile

    if on_progress:
        on_progress("Extrayendo archivos...", "")

    with tarfile.open(tar_path, "r:xz") as tar:
        # Extraer solo archivos seguros
        for member in tar.getmembers():
            member_path = os.path.join(app_dir, member.name)
            if not os.path.abspath(member_path).startswith(os.path.abspath(app_dir)):
                continue
            tar.extract(member, app_dir)


def _install_from_appimage(appimage_path: str, app_dir: str, on_progress: Callable | None = None):
    """Reemplaza la AppImage actual."""
    if on_progress:
        on_progress("Reemplazando AppImage...", "")

    current = os.path.join(app_dir, "AudioClass")
    if os.path.exists(current):
        os.remove(current)
    shutil.copy2(appimage_path, current)
    os.chmod(current, 0o755)


def restart_app():
    """Reinicia la aplicación."""
    app_script = os.path.join(str(Path(__file__).parent), "audioclass_v91.py")

    if SO == "Windows":
        # Windows: usar start para lanzar nuevo proceso
        subprocess.Popen(
            [sys.executable, app_script],
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    elif SO == "Darwin":
        # macOS: usar open
        subprocess.Popen(["open", "-a", "Python", app_script])
    else:
        # Linux: usar nohup
        subprocess.Popen(
            [sys.executable, app_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
        )

    # Cerrar el proceso actual
    if SO == "Linux":
        os._exit(0)
    else:
        sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════
# Funciones específicas para AppImage (Linux)
# ═══════════════════════════════════════════════════════════════════════════


def is_appimage() -> bool:
    """Detecta si AudioClass se ejecuta como AppImage."""
    # AppImage establece APPIMAGE y APPDIR variables de entorno
    return bool(os.environ.get("APPIMAGE"))


def get_appimage_path() -> str | None:
    """Retorna la ruta al AppImage actual."""
    return os.environ.get("APPIMAGE")


def get_appimage_update_info() -> str | None:
    """Extrae la update info embebida en el AppImage.

    La update info tiene el formato:
    gh-releases-zsync|owner|repo|tag|filename.zsync
    """
    appimage_path = get_appimage_path()
    if not appimage_path or not os.path.exists(appimage_path):
        return None

    try:
        # Leer los últimos 10KB del AppImage (donde está la update info)
        with open(appimage_path, "rb") as f:
            f.seek(max(0, os.path.getsize(appimage_path) - 10240))
            tail = f.read().decode("utf-8", errors="replace")

        # Buscar patrón de update info
        # gh-releases-zsync|owner|repo|tag|filename.zsync
        match = re.search(r"(gh-releases-zsync\|[\w.-]+\|[\w.-]+\|[\w.-]+\|[\w._-]+\.zsync)", tail)
        if match:
            return match.group(1)

        # También buscar URL directa a .zsync
        match = re.search(r"(https?://[\w./-]+\.zsync)", tail)
        if match:
            return match.group(1)

    except Exception:
        pass

    return None


def check_appimage_update(
    current_version: str,
    timeout: int = 10,
) -> dict:
    """Verifica si hay una actualización AppImage disponible.

    Usa la update info embebida para buscar el archivo .zsync
    y determinar si hay una versión más reciente.

    Args:
        current_version: Versión actual del AppImage.
        timeout: Timeout de la petición HTTP.

    Returns:
        dict con:
            - update_available (bool)
            - latest_version (str)
            - zsync_url (str): URL del archivo .zsync
            - zsync_size (int): Tamaño del .zsync en bytes
            - full_url (str): URL del AppImage completo (fallback)
            - error (str|None)
    """
    result = {
        "update_available": False,
        "latest_version": "",
        "current_version": current_version,
        "zsync_url": "",
        "zsync_size": 0,
        "full_url": "",
        "error": None,
    }

    # Obtener update info del AppImage
    update_info = get_appimage_update_info()
    if not update_info:
        # Sin update info: usar método estándar de GitHub
        result_std = check_for_updates(current_version, timeout)
        result.update(result_std)
        return result

    try:
        # Parsear update info
        # Formato: gh-releases-zsync|owner|repo|tag|filename.zsync
        parts = update_info.split("|")
        if len(parts) == 5 and parts[0] == "gh-releases-zsync":
            owner, repo, tag, filename = parts[1], parts[2], parts[3], parts[4]

            # Construir URL del .zsync
            if tag == "latest":
                zsync_url = f"https://github.com/{owner}/{repo}/releases/latest/download/{filename}"
            else:
                zsync_url = f"https://github.com/{owner}/{repo}/releases/download/{tag}/{filename}"

            # Verificar si el .zsync existe
            r = requests.head(zsync_url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                result["zsync_url"] = zsync_url
                result["zsync_size"] = int(r.headers.get("Content-Length", 0))

                # Comparar versiones
                current = _parse_version(current_version)
                latest = _parse_version(tag.lstrip("v")) if tag != "latest" else _parse_version("")

                if tag == "latest" or latest > current:
                    result["update_available"] = True
                    result["latest_version"] = tag.lstrip("v") if tag != "latest" else "latest"

        elif update_info.startswith("http"):
            # URL directa al .zsync
            r = requests.head(update_info, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                result["zsync_url"] = update_info
                result["zsync_size"] = int(r.headers.get("Content-Length", 0))
                result["update_available"] = True
                result["latest_version"] = "latest"

    except requests.exceptions.Timeout:
        result["error"] = "Tiempo de espera agotado"
    except requests.exceptions.ConnectionError:
        result["error"] = "Sin conexión a internet"
    except Exception as e:
        result["error"] = str(e)[:100]

    return result


def update_appimage(
    zsync_url: str,
    on_progress: Callable[[int, int, str], None] | None = None,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Actualiza el AppImage usando zsync (descarga diferencial).

    Args:
        zsync_url: URL del archivo .zsync.
        on_progress: Callback(bytes_downloaded, total_bytes, status_msg).
        timeout: Timeout de la descarga en segundos.

    Returns:
        Tuple (success, message).
    """
    appimage_path = get_appimage_path()
    if not appimage_path:
        return False, "No se encontró la ruta del AppImage"

    # Intentar usar appimageupdatetool si está disponible
    update_tool = shutil.which("appimageupdatetool") or shutil.which("AppImageUpdate")

    if update_tool:
        return _update_with_tool(update_tool, appimage_path, on_progress, timeout)
    else:
        return _update_with_zsync(zsync_url, appimage_path, on_progress, timeout)


def _update_with_tool(
    tool_path: str,
    appimage_path: str,
    on_progress: Callable | None = None,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Actualiza usando appimageupdatetool (si está instalado)."""
    try:
        if on_progress:
            on_progress(0, 0, "Ejecutando appimageupdatetool...")

        result = subprocess.run(
            [tool_path, appimage_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            return True, "AppImage actualizado correctamente"
        else:
            error_msg = result.stderr.strip()[:200]
            return False, f"Error en appimageupdatetool: {error_msg}"

    except subprocess.TimeoutExpired:
        return False, "Timeout: la actualización tardó demasiado"
    except Exception as e:
        return False, f"Error: {str(e)[:100]}"


def _update_with_zsync(
    zsync_url: str,
    appimage_path: str,
    on_progress: Callable | None = None,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Actualiza descargando el AppImage completo (fallback sin zsync).

    Si zsync no está disponible, descarga el AppImage completo
    y reemplaza el actual.
    """
    try:
        # Derivar URL del AppImage completo desde la URL del .zsync
        # .zsync → .AppImage
        full_url = zsync_url.replace(".zsync", "")

        if on_progress:
            on_progress(0, 0, "Descargando AppImage completo...")

        # Descargar AppImage completo
        dest_dir = os.path.dirname(appimage_path)
        dest_path = os.path.join(dest_dir, "AudioClass_new.AppImage")

        headers = {"Accept": "application/octet-stream"}
        r = requests.get(full_url, headers=headers, timeout=timeout, stream=True)

        if r.status_code != 200:
            return False, f"Error HTTP {r.status_code} al descargar"

        total_size = int(r.headers.get("Content-Length", 0))
        downloaded = 0

        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(
                            downloaded,
                            total_size,
                            f"Descargado {downloaded // 1024 // 1024}MB / {total_size // 1024 // 1024}MB",
                        )

        # Hacer ejecutable
        os.chmod(dest_path, 0o755)

        # Reemplazar AppImage actual
        backup_path = appimage_path + ".old"
        os.rename(appimage_path, backup_path)
        os.rename(dest_path, appimage_path)

        # Eliminar backup después de un delay
        try:
            os.unlink(backup_path)
        except Exception:
            pass

        if on_progress:
            on_progress(total_size, total_size, "AppImage actualizado")

        return True, "AppImage actualizado correctamente"

    except requests.exceptions.Timeout:
        return False, "Timeout durante la descarga"
    except requests.exceptions.ConnectionError:
        return False, "Conexión perdida durante la descarga"
    except Exception as e:
        return False, f"Error: {str(e)[:100]}"


def get_appimage_version() -> str | None:
    """Obtiene la versión del AppImage actual desde su nombre o metadatos."""
    appimage_path = get_appimage_path()
    if not appimage_path:
        return None

    # Intentar extraer versión del nombre del archivo
    basename = os.path.basename(appimage_path)
    match = re.search(r"v?(\d+\.\d+\.\d+)", basename)
    if match:
        return match.group(1)

    # Intentar desde .AppImage_update yOffset
    try:
        # Buscar en los últimos bytes del AppImage
        with open(appimage_path, "rb") as f:
            f.seek(max(0, os.path.getsize(appimage_path) - 10240))
            tail = f.read().decode("utf-8", errors="replace")
            match = re.search(r'"version"\s*:\s*"([\d.]+)"', tail)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None


if __name__ == "__main__":
    ver = sys.argv[1] if len(sys.argv) > 1 else "9.1.0"
    result = check_for_updates(ver)
    if result["error"]:
        print(f"Error: {result['error']}")
    elif result["update_available"]:
        print(f"Nueva versión disponible: {result['latest_version']} (actual: {result['current_version']})")
        print(f"Descargar: {result['release_url']}")
        if result["assets"]:
            asset = find_download_asset(result["assets"])
            if asset:
                print(f"Asset: {asset['name']} ({asset['size'] // 1024}KB)")
    else:
        print(f"Estás en la última versión ({result['current_version']})")
