"""services/model_manager.py — Gestor unificado de modelos de IA y almacenamiento.

Centraliza la resolución de rutas, verificación de disponibilidad, descargas
reanudables (HTTP Range), cálculo de integridad SHA-256 y ciclo de vida en disco
para motores Whisper (openai y CTranslate2), Sherpa Parakeet y Silero VAD.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelSpec:
    """Especificación y metadatos de un modelo."""

    key: str
    name: str
    engine_type: str  # "whisper", "parakeet", "silero"
    files: list[str] = field(default_factory=list)
    url: str | None = None
    sha256: str | None = None
    archive_format: str | None = None  # "tar.bz2", "zip", or None
    size_mb: float = 0.0
    description: str = ""


# ── Registro de Modelos Oficiales ─────────────────────────────────────────────

MODEL_REGISTRY: dict[str, ModelSpec] = {
    "whisper-tiny": ModelSpec(
        key="whisper-tiny",
        name="Whisper Tiny",
        engine_type="whisper",
        files=["tiny.pt"],
        url="https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26fde3f8dd46151de06477e9e60341540fe246/tiny.pt",
        sha256="65147644a518d12f04e32d6f3b26fde3f8dd46151de06477e9e60341540fe246",
        size_mb=75.0,
        description="Modelo Whisper más liviano y rápido.",
    ),
    "whisper-base": ModelSpec(
        key="whisper-base",
        name="Whisper Base",
        engine_type="whisper",
        files=["base.pt"],
        url="https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f833f6a29558de6263b8ab8/base.pt",
        sha256="ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f833f6a29558de6263b8ab8",
        size_mb=142.0,
        description="Modelo Whisper balanceado para clases estándar.",
    ),
    "whisper-small": ModelSpec(
        key="whisper-small",
        name="Whisper Small",
        engine_type="whisper",
        files=["small.pt"],
        url="https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d7205242c443a30ff7f63e645dc2e0766a75a/small.pt",
        sha256="9ecf779972d90ba49c06d968637d7205242c443a30ff7f63e645dc2e0766a75a",
        size_mb=466.0,
        description="Modelo Whisper de alta precisión.",
    ),
    "parakeet-tdt-0.6b-v3": ModelSpec(
        key="parakeet-tdt-0.6b-v3",
        name="NVIDIA Parakeet TDT 0.6B v3 (INT8)",
        engine_type="parakeet",
        files=["encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"],
        url=(
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
            "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2"
        ),
        archive_format="tar.bz2",
        size_mb=640.0,
        description="Motor Transducer ultrarrápido para CPU con INT8.",
    ),
}


class ModelManager:
    """Gestor unificado de modelos de IA."""

    _instance: ModelManager | None = None
    _lock = threading.Lock()

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.user_cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "audioclass", "models")
        self._dl_lock = threading.Lock()

    @classmethod
    def get_instance(cls, base_dir: str | None = None) -> ModelManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(base_dir)
            return cls._instance

    # ── Resolución de Rutas ───────────────────────────────────────────────────

    def get_models_dir(self, engine_type: str = "whisper") -> str:
        """Devuelve el directorio prioritario para almacenar/buscar modelos."""
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
            if engine_type == "ct2":
                p = os.path.join(base, "models_ct2")
            elif engine_type == "parakeet":
                p = os.path.join(base, "models_parakeet")
            else:
                p = os.path.join(base, "models")
            if os.path.isdir(p):
                return p

        # Directorio de espacio de trabajo local
        if engine_type == "ct2":
            local = os.path.join(self.base_dir, "models_ct2")
        elif engine_type == "parakeet":
            local = os.path.join(self.base_dir, "models_parakeet")
        else:
            local = os.path.join(self.base_dir, "models")

        if os.path.isdir(local):
            return local

        # Fallback al directorio del usuario
        user_dir = os.path.join(self.user_cache_dir, engine_type)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def resolve_model_path(self, engine_type: str, model_name: str) -> str | None:
        """Encuentra la ruta a un modelo según su tipo y nombre."""
        model_name = model_name.strip().lower()

        # 1. Sherpa Parakeet
        if engine_type == "parakeet":
            dir_name = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8"
            candidate_roots = [
                os.path.join(self.base_dir, "models_parakeet"),
                os.path.join(self.user_cache_dir, "parakeet"),
            ]
            if getattr(sys, "frozen", False):
                base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
                candidate_roots.insert(0, os.path.join(base, "models_parakeet"))

            for root in candidate_roots:
                full_path = os.path.join(root, dir_name)
                if self._check_parakeet_files(full_path):
                    return full_path
            return None

        # 2. CTranslate2 (faster-whisper)
        if engine_type == "ct2":
            candidate_roots = [
                os.path.join(self.base_dir, "models_ct2"),
                os.path.join(self.user_cache_dir, "ct2"),
            ]
            if getattr(sys, "frozen", False):
                base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
                candidate_roots.insert(0, os.path.join(base, "models_ct2"))

            for root in candidate_roots:
                for name_variant in (model_name, "tiny", "base"):
                    d = os.path.join(root, name_variant)
                    if os.path.isdir(d) and os.path.isfile(os.path.join(d, "model.bin")):
                        return d
            return None

        # 3. Whisper OpenAI (.pt)
        candidate_roots = [
            os.path.join(self.base_dir, "models"),
            os.path.expanduser("~/.cache/whisper"),
            os.path.join(self.user_cache_dir, "whisper"),
        ]
        if getattr(sys, "frozen", False):
            base = getattr(sys, "_MEIPASS", "") or os.path.dirname(os.path.abspath(sys.executable))
            candidate_roots.insert(0, os.path.join(base, "models"))

        for root in candidate_roots:
            p = os.path.join(root, f"{model_name}.pt")
            if os.path.isfile(p) and os.path.getsize(p) > 1024:
                return p

        return None

    def _check_parakeet_files(self, model_dir: str) -> bool:
        """Verifica que todos los archivos requeridos de Parakeet estén presentes."""
        required = ["encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"]
        return os.path.isdir(model_dir) and all(
            os.path.isfile(os.path.join(model_dir, f)) and os.path.getsize(os.path.join(model_dir, f)) > 0
            for f in required
        )

    def is_model_available(self, engine_type: str, model_name: str) -> bool:
        """Determina si un modelo está completamente descargado y listo para usar."""
        return self.resolve_model_path(engine_type, model_name) is not None

    # ── Integridad y Checksums ────────────────────────────────────────────────

    @staticmethod
    def calculate_sha256(filepath: str, block_size: int = 65536) -> str:
        """Calcula el hash SHA-256 de un archivo en bloques."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(block_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def verify_checksum(cls, filepath: str, expected_sha256: str) -> bool:
        """Compara el checksum de forma segura contra tiempo de ejecución."""
        if not os.path.isfile(filepath):
            return False
        calculated = cls.calculate_sha256(filepath)
        return hmac.compare_digest(calculated.lower(), expected_sha256.strip().lower())

    # ── Descarga Reanudable (HTTP Range) ──────────────────────────────────────

    def download_with_resume(
        self,
        url: str,
        dest_path: str,
        expected_sha256: str | None = None,
        progress_callback: Callable[[int, int, float, float], None] | None = None,
        cancel_event: threading.Event | None = None,
        chunk_size: int = 65536,
        timeout: float = 30.0,
    ) -> str:
        """Descarga un archivo con soporte de reanudación (Range) y verificación SHA-256.

        Argumentos para `progress_callback`: (descargado_bytes, total_bytes, porcentaje, velocidad_mb_s)
        """
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        part_path = dest_path + ".part"

        # Verificar si ya existe el archivo final y coincide el hash
        if os.path.isfile(dest_path):
            if expected_sha256:
                if self.verify_checksum(dest_path, expected_sha256):
                    if progress_callback:
                        size = os.path.getsize(dest_path)
                        progress_callback(size, size, 100.0, 0.0)
                    return dest_path
                else:
                    os.remove(dest_path)
            else:
                return dest_path

        existing_bytes = os.path.getsize(part_path) if os.path.isfile(part_path) else 0

        req = urllib.request.Request(url)
        req.add_header("User-Agent", "AudioClass/9.1")

        if existing_bytes > 0:
            req.add_header("Range", f"bytes={existing_bytes}-")

        mode = "ab" if existing_bytes > 0 else "wb"
        downloaded = existing_bytes
        total_size = 0

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status = getattr(response, "status", 200)

                # Si el servidor no soporta Range o devolvió 200 completo, resetear
                if existing_bytes > 0 and status == 200:
                    mode = "wb"
                    downloaded = 0
                    existing_bytes = 0

                content_len = response.headers.get("Content-Length")
                if content_len:
                    total_size = int(content_len) + existing_bytes
                else:
                    total_size = 0

                start_time = time.time()
                bytes_since_start = 0

                with open(part_path, mode) as f:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            raise InterruptedError("Descarga cancelada por el usuario.")

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        bytes_since_start += len(chunk)

                        elapsed = max(0.001, time.time() - start_time)
                        speed_mb_s = (bytes_since_start / (1024 * 1024)) / elapsed
                        pct = (downloaded / total_size * 100.0) if total_size > 0 else 0.0

                        if progress_callback:
                            progress_callback(downloaded, total_size, pct, speed_mb_s)

        except urllib.error.HTTPError as e:
            if e.code == 416:  # Requested Range Not Satisfiable (ya descargado completo)
                pass
            else:
                raise

        # Verificación de integridad si se proporcionó SHA-256
        if expected_sha256:
            if not self.verify_checksum(part_path, expected_sha256):
                if os.path.exists(part_path):
                    os.remove(part_path)
                raise ValueError("Error de integridad: el hash SHA-256 del archivo no coincide.")

        # Renombrado atómico
        if os.path.exists(dest_path):
            os.remove(dest_path)
        shutil.move(part_path, dest_path)

        if progress_callback and total_size > 0:
            progress_callback(total_size, total_size, 100.0, 0.0)

        return dest_path

    # ── Asegurar Modelos (Descarga + Extracción) ───────────────────────────────

    def ensure_parakeet(
        self,
        progress_callback: Callable[[str, Any], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> str:
        """Descarga y extrae el modelo Parakeet TDT INT8 si no está presente."""
        existing = self.resolve_model_path("parakeet", "parakeet-tdt-0.6b-v3")
        if existing:
            return existing

        with self._dl_lock:
            # Comprobar de nuevo dentro del lock
            existing = self.resolve_model_path("parakeet", "parakeet-tdt-0.6b-v3")
            if existing:
                return existing

            target_dir = os.path.join(self.base_dir, "models_parakeet")
            os.makedirs(target_dir, exist_ok=True)

            spec = MODEL_REGISTRY["parakeet-tdt-0.6b-v3"]
            archive_path = os.path.join(target_dir, "parakeet.tar.bz2")

            def _dl_cb(count_b, total_b, pct, speed):
                if progress_callback and total_b > 0:
                    mb_curr = count_b / (1024 * 1024)
                    mb_tot = total_b / (1024 * 1024)
                    msg = f"{int(pct)}% ({mb_curr:.0f}/{mb_tot:.0f} MB - {speed:.1f} MB/s)"
                    progress_callback("downloading", msg)

            self.download_with_resume(
                url=spec.url or "",
                dest_path=archive_path,
                expected_sha256=spec.sha256,
                progress_callback=_dl_cb,
                cancel_event=cancel_event,
            )

            if progress_callback:
                progress_callback("extracting", "Descomprimiendo modelo Parakeet...")

            with tarfile.open(archive_path, "r:bz2") as tar:
                tar.extractall(target_dir)

            if os.path.exists(archive_path):
                os.remove(archive_path)

            resolved = self.resolve_model_path("parakeet", "parakeet-tdt-0.6b-v3")
            if not resolved:
                raise RuntimeError("No se pudo resolver el modelo Parakeet tras la extracción.")
            return resolved

    def ensure_whisper_model(
        self,
        model_name: str = "base",
        backend: str = "faster",
        progress_callback: Callable[[str, Any], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> str:
        """Garantiza la disponibilidad del modelo Whisper pedido."""
        model_name = model_name.strip().lower()

        if backend == "faster":
            resolved = self.resolve_model_path("ct2", model_name)
            if resolved:
                return resolved

            # Intento de descarga automática con huggingface_hub si está presente
            target_dir = os.path.join(self.get_models_dir("ct2"), model_name)
            try:
                from huggingface_hub import snapshot_download

                if progress_callback:
                    progress_callback("downloading", f"Descargando CT2 {model_name}...")

                snapshot_download(
                    repo_id=f"Systran/faster-whisper-{model_name}",
                    local_dir=target_dir,
                )
                return target_dir
            except Exception:
                # Retorna el nombre si faster-whisper maneja su propia descarga internamente
                return model_name

        # OpenAI Whisper (.pt)
        resolved = self.resolve_model_path("whisper", model_name)
        if resolved:
            return resolved

        spec_key = f"whisper-{model_name}"
        if spec_key in MODEL_REGISTRY:
            spec = MODEL_REGISTRY[spec_key]
            dest = os.path.join(self.get_models_dir("whisper"), f"{model_name}.pt")

            def _dl_cb(count_b, total_b, pct, speed):
                if progress_callback and total_b > 0:
                    mb_curr = count_b / (1024 * 1024)
                    mb_tot = total_b / (1024 * 1024)
                    progress_callback("downloading", f"{int(pct)}% ({mb_curr:.0f}/{mb_tot:.0f} MB)")

            return self.download_with_resume(
                url=spec.url or "",
                dest_path=dest,
                expected_sha256=spec.sha256,
                progress_callback=_dl_cb,
                cancel_event=cancel_event,
            )

        return model_name

    # ── Mantenimiento y Estadísticas ──────────────────────────────────────────

    def get_storage_summary(self) -> dict[str, Any]:
        """Calcula el espacio ocupado por modelos en disco."""
        summary: dict[str, Any] = {
            "models_dir_mb": 0.0,
            "models_ct2_mb": 0.0,
            "models_parakeet_mb": 0.0,
            "user_cache_mb": 0.0,
            "total_mb": 0.0,
            "models": [],
        }

        def _dir_size_mb(path: str) -> float:
            if not os.path.isdir(path):
                return 0.0
            total = 0
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total += os.path.getsize(fp)
                    except OSError:
                        pass
            return round(total / (1024 * 1024), 2)

        summary["models_dir_mb"] = _dir_size_mb(os.path.join(self.base_dir, "models"))
        summary["models_ct2_mb"] = _dir_size_mb(os.path.join(self.base_dir, "models_ct2"))
        summary["models_parakeet_mb"] = _dir_size_mb(os.path.join(self.base_dir, "models_parakeet"))
        summary["user_cache_mb"] = _dir_size_mb(self.user_cache_dir)
        summary["total_mb"] = round(
            summary["models_dir_mb"]
            + summary["models_ct2_mb"]
            + summary["models_parakeet_mb"]
            + summary["user_cache_mb"],
            2,
        )

        for key, spec in MODEL_REGISTRY.items():
            avail = self.is_model_available(spec.engine_type, spec.name.split()[-1].lower())
            summary["models"].append(
                {
                    "key": key,
                    "name": spec.name,
                    "engine_type": spec.engine_type,
                    "available": avail,
                    "path": self.resolve_model_path(spec.engine_type, spec.name.split()[-1].lower()),
                }
            )

        return summary

    def clean_cache(self, engine_type: str | None = None) -> int:
        """Limpia archivos temporales `.part` y caché residual. Retorna bytes liberados."""
        freed = 0
        dirs_to_clean = [
            os.path.join(self.base_dir, "models"),
            os.path.join(self.base_dir, "models_ct2"),
            os.path.join(self.base_dir, "models_parakeet"),
            self.user_cache_dir,
        ]

        for d in dirs_to_clean:
            if not os.path.isdir(d):
                continue
            for root, _, files in os.walk(d):
                for f in files:
                    if f.endswith(".part") or f.endswith(".tmp"):
                        fp = os.path.join(root, f)
                        try:
                            sz = os.path.getsize(fp)
                            os.remove(fp)
                            freed += sz
                        except OSError:
                            pass
        return freed


def get_default_model_manager() -> ModelManager:
    """Acceso conveniente a la instancia global de ModelManager."""
    return ModelManager.get_instance()
