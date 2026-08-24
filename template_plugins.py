#!/usr/bin/env python3
"""
template_plugins.py — Sistema de plugins para templates de análisis IA
======================================================================

Permite crear, cargar, validar y ejecutar templates de análisis personalizados.

Cada plugin es un archivo JSON o Python que define:
  - Nombre, descripción, icono
  - Prompt con placeholder {TEXT}
  - Parámetros del modelo (temperature, max_tokens)
  - Metadatos (autor, versión, licencia)

Directorios de plugins:
  - plugins/builtin/     — Templates incorporados
  - plugins/custom/      — Templates del usuario
  - ~/.audioclass/plugins/ — Plugins globales

Uso:
    from template_plugins import PluginManager

    manager = PluginManager()
    manager.discover()

    # Listar templates
    templates = manager.get_all_templates()

    # Ejecutar un template
    result = manager.run_template("resumen", text, engine)
"""

import importlib.machinery
import importlib.util
import json
import os
import sys
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Plugin Metadata ──────────────────────────────────────────────────────────


@dataclass
class PluginMeta:
    """Metadatos de un plugin de template."""

    id: str
    name: str
    description: str
    author: str = "AudioClass"
    version: str = "1.0.0"
    license: str = "MIT"
    icon: str = ""
    tags: list[str] = field(default_factory=list)
    min_app_version: str = ""
    source_path: str = ""
    is_builtin: bool = False
    is_enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "license": self.license,
            "icon": self.icon,
            "tags": self.tags,
            "min_app_version": self.min_app_version,
            "source_path": self.source_path,
            "is_builtin": self.is_builtin,
            "is_enabled": self.is_enabled,
        }


@dataclass
class PluginTemplate:
    """Un template de análisis cargado desde un plugin."""

    meta: PluginMeta
    prompt: str
    icon: str = ""
    desc: str = ""
    max_tokens: int = 4096
    temperature: float = 0.3
    output_format: str = "markdown"  # markdown, json, text
    language_hints: list[str] = field(default_factory=lambda: ["es", "en"])
    _compiled_prompt: str | None = None

    def render_prompt(self, text: str, **kwargs) -> str:
        """Renderiza el prompt con el texto y variables adicionales."""
        prompt = self.prompt.replace("{TEXT}", text)
        for key, value in kwargs.items():
            prompt = prompt.replace(f"{{{key.upper()}}}", str(value))
        return prompt

    def to_dict(self) -> dict:
        return {
            "meta": self.meta.to_dict(),
            "prompt": self.prompt,
            "icon": self.icon,
            "desc": self.desc,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "output_format": self.output_format,
            "language_hints": self.language_hints,
        }


# ── Plugin Loader ────────────────────────────────────────────────────────────


class PluginLoader:
    """Carga plugins desde archivos JSON o Python."""

    @staticmethod
    def load_json(path: str) -> PluginTemplate | None:
        """Carga un template desde un archivo JSON."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            # Validar campos requeridos
            required = ["id", "name", "prompt"]
            for field_name in required:
                if field_name not in data:
                    print(f"[PluginLoader] Campo requerido '{field_name}' no encontrado en {path}")
                    return None

            meta = PluginMeta(
                id=data["id"],
                name=data["name"],
                description=data.get("description", ""),
                author=data.get("author", "Unknown"),
                version=data.get("version", "1.0.0"),
                license=data.get("license", "MIT"),
                icon=data.get("icon", ""),
                tags=data.get("tags", []),
                min_app_version=data.get("min_app_version", ""),
                source_path=path,
                is_builtin=data.get("is_builtin", False),
                is_enabled=data.get("is_enabled", True),
            )

            return PluginTemplate(
                meta=meta,
                prompt=data["prompt"],
                icon=data.get("icon", meta.icon),
                desc=data.get("desc", meta.description),
                max_tokens=data.get("max_tokens", 4096),
                temperature=data.get("temperature", 0.3),
                output_format=data.get("output_format", "markdown"),
                language_hints=data.get("language_hints", ["es", "en"]),
            )

        except json.JSONDecodeError as e:
            print(f"[PluginLoader] Error de JSON en {path}: {e}")
            return None
        except Exception as e:
            print(f"[PluginLoader] Error cargando {path}: {e}")
            return None

    @staticmethod
    def load_python(path: str) -> PluginTemplate | None:
        """Carga un template desde un archivo Python.

        El archivo Python debe definir:
            PLUGIN_META = { ... }  # Metadatos
            PLUGIN_TEMPLATE = {   # Template
                "prompt": "...",
                "icon": "...",
                ...
            }

        O una función:
            def register(registrar):
                registrar(PluginTemplate(...))
        """
        try:
            module_name = Path(path).stem
            loader = importlib.machinery.SourceFileLoader(module_name, path)
            spec = importlib.util.spec_from_loader(module_name, loader)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            loader.exec_module(module)

            # Opción 1: Usar register() function
            if hasattr(module, "register"):
                templates = []

                def _collector(template):
                    if isinstance(template, PluginTemplate):
                        templates.append(template)

                module.register(_collector)

                if templates:
                    return templates[0]  # Retornar el primero

            # Opción 2: Usar PLUGIN_META + PLUGIN_TEMPLATE
            if hasattr(module, "PLUGIN_META") and hasattr(module, "PLUGIN_TEMPLATE"):
                meta_data = module.PLUGIN_META
                template_data = module.PLUGIN_TEMPLATE

                meta = PluginMeta(
                    id=meta_data.get("id", module_name),
                    name=meta_data.get("name", module_name),
                    description=meta_data.get("description", ""),
                    author=meta_data.get("author", "Unknown"),
                    version=meta_data.get("version", "1.0.0"),
                    license=meta_data.get("license", "MIT"),
                    icon=meta_data.get("icon", ""),
                    tags=meta_data.get("tags", []),
                    min_app_version=meta_data.get("min_app_version", ""),
                    source_path=path,
                    is_builtin=meta_data.get("is_builtin", False),
                    is_enabled=meta_data.get("is_enabled", True),
                )

                return PluginTemplate(
                    meta=meta,
                    prompt=template_data["prompt"],
                    icon=template_data.get("icon", meta.icon),
                    desc=template_data.get("desc", meta.description),
                    max_tokens=template_data.get("max_tokens", 4096),
                    temperature=template_data.get("temperature", 0.3),
                    output_format=template_data.get("output_format", "markdown"),
                    language_hints=template_data.get("language_hints", ["es", "en"]),
                )

            print(f"[PluginLoader] {path}: No se encontró register() ni PLUGIN_META + PLUGIN_TEMPLATE")
            return None

        except Exception as e:
            print(f"[PluginLoader] Error cargando Python plugin {path}: {e}")
            traceback.print_exc()
            return None


# ── Plugin Validator ─────────────────────────────────────────────────────────


class PluginValidator:
    """Valida plugins antes de cargarlos."""

    @staticmethod
    def validate(template: PluginTemplate) -> tuple[bool, list[str]]:
        """Valida un template. Retorna (es_válido, lista_errores)."""
        errors = []

        # Validar meta
        if not template.meta.id:
            errors.append("Plugin ID vacío")
        if not template.meta.name:
            errors.append("Plugin name vacío")
        if len(template.meta.id) < 3:
            errors.append("Plugin ID debe tener al menos 3 caracteres")
        if not template.meta.id.isalnum() and not all(c.isalnum() or c in "-_" for c in template.meta.id):
            errors.append("Plugin ID solo puede contener letras, números, guiones y guiones bajos")

        # Validar prompt
        if not template.prompt:
            errors.append("Prompt vacío")
        elif "{TEXT}" not in template.prompt:
            errors.append("Prompt no contiene placeholder {TEXT}")

        # Validar parámetros
        if template.max_tokens < 100 or template.max_tokens > 32768:
            errors.append(f"max_tokens fuera de rango: {template.max_tokens}")
        if template.temperature < 0 or template.temperature > 2:
            errors.append(f"temperature fuera de rango: {template.temperature}")

        return len(errors) == 0, errors

    @staticmethod
    def validate_json_file(path: str) -> tuple[bool, list[str]]:
        """Valida un archivo JSON de plugin sin cargarlo."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            errors = []

            required = ["id", "name", "prompt"]
            for field_name in required:
                if field_name not in data:
                    errors.append(f"Campo requerido '{field_name}' no encontrado")

            if "prompt" in data and "{TEXT}" not in data["prompt"]:
                errors.append("Prompt no contiene placeholder {TEXT}")

            return len(errors) == 0, errors

        except json.JSONDecodeError as e:
            return False, [f"JSON inválido: {e}"]
        except FileNotFoundError:
            return False, [f"Archivo no encontrado: {path}"]
        except Exception as e:
            return False, [str(e)]


# ── Plugin Manager ──────────────────────────────────────────────────────────


class PluginManager:
    """Gestor central de plugins de templates."""

    def __init__(self, extra_dirs: list[str] | None = None):
        self._templates: dict[str, PluginTemplate] = {}
        self._plugin_dirs: list[str] = []
        self._watchers: list[Callable] = []
        self._last_scan: float = 0

        # Directorios por defecto
        base = Path(__file__).parent
        self._plugin_dirs.append(str(base / "plugins" / "builtin"))
        self._plugin_dirs.append(str(base / "plugins" / "custom"))

        # Directorio global del usuario
        user_dir = Path.home() / ".audioclass" / "plugins"
        self._plugin_dirs.append(str(user_dir))

        # Directorios adicionales
        if extra_dirs:
            self._plugin_dirs.extend(extra_dirs)

        # Crear directorios si no existen
        for d in self._plugin_dirs:
            os.makedirs(d, exist_ok=True)

    def discover(self, force: bool = False) -> int:
        """Descubre y carga todos los plugins.

        Returns:
            Número de plugins cargados.
        """
        if not force and (time.time() - self._last_scan) < 5:
            return len(self._templates)

        self._templates.clear()
        loaded = 0

        for plugin_dir in self._plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue

            # Cargar JSON plugins
            for fname in sorted(os.listdir(plugin_dir)):
                fpath = os.path.join(plugin_dir, fname)

                if fname.endswith(".json"):
                    template = PluginLoader.load_json(fpath)
                    if template:
                        valid, errors = PluginValidator.validate(template)
                        if valid:
                            self._templates[template.meta.id] = template
                            loaded += 1
                        else:
                            print(f"[PluginManager] Plugin inválido {fname}: {errors}")

                elif fname.endswith(".py") and not fname.startswith("_"):
                    template = PluginLoader.load_python(fpath)
                    if template:
                        valid, errors = PluginValidator.validate(template)
                        if valid:
                            self._templates[template.meta.id] = template
                            loaded += 1
                        else:
                            print(f"[PluginManager] Plugin inválido {fname}: {errors}")

        self._last_scan = time.time()
        return loaded

    def get_template(self, template_id: str) -> PluginTemplate | None:
        """Obtiene un template por ID."""
        return self._templates.get(template_id)

    def get_all_templates(self) -> dict[str, PluginTemplate]:
        """Devuelve todos los templates cargados."""
        return dict(self._templates)

    def get_enabled_templates(self) -> dict[str, PluginTemplate]:
        """Devuelve solo los templates habilitados."""
        return {k: v for k, v in self._templates.items() if v.meta.is_enabled}

    def get_builtin_templates(self) -> dict[str, PluginTemplate]:
        """Devuelve los templates incorporados."""
        return {k: v for k, v in self._templates.items() if v.meta.is_builtin}

    def get_custom_templates(self) -> dict[str, PluginTemplate]:
        """Devuelve los templates personalizados del usuario."""
        return {k: v for k, v in self._templates.items() if not v.meta.is_builtin}

    def enable_template(self, template_id: str) -> bool:
        """Habilita un template."""
        if template_id in self._templates:
            self._templates[template_id].meta.is_enabled = True
            return True
        return False

    def disable_template(self, template_id: str) -> bool:
        """Deshabilita un template."""
        if template_id in self._templates:
            self._templates[template_id].meta.is_enabled = False
            return True
        return False

    def install_plugin(self, source_path: str) -> tuple[bool, str]:
        """Instala un plugin desde un archivo.

        Copia el archivo al directorio custom/ y lo carga.
        """
        import shutil

        if not os.path.exists(source_path):
            return False, f"Archivo no encontrado: {source_path}"

        # Validar antes de copiar
        if source_path.endswith(".json"):
            valid, errors = PluginValidator.validate_json_file(source_path)
            if not valid:
                return False, f"Plugin inválido: {', '.join(errors)}"

        # Copiar al directorio custom
        custom_dir = self._plugin_dirs[1]  # plugins/custom/
        dest = os.path.join(custom_dir, os.path.basename(source_path))

        if os.path.exists(dest):
            return False, f"Ya existe un plugin con el nombre: {os.path.basename(source_path)}"

        shutil.copy2(source_path, dest)

        # Recargar
        self.discover(force=True)

        return True, f"Plugin instalado: {os.path.basename(source_path)}"

    def uninstall_plugin(self, template_id: str) -> tuple[bool, str]:
        """Desinstala un plugin personalizado."""
        template = self._templates.get(template_id)
        if not template:
            return False, f"Plugin no encontrado: {template_id}"

        if template.meta.is_builtin:
            return False, "No se pueden desinstalar plugins incorporados"

        source = template.meta.source_path
        if source and os.path.exists(source):
            os.remove(source)

        self._templates.pop(template_id, None)
        return True, f"Plugin desinstalado: {template_id}"

    def create_plugin(self, plugin_data: dict) -> tuple[bool, str]:
        """Crea un nuevo plugin personalizado.

        plugin_data debe contener:
            id, name, prompt (requerido)
            description, icon, author, version, etc. (opcional)
        """
        # Validar
        required = ["id", "name", "prompt"]
        for field_name in required:
            if field_name not in plugin_data:
                return False, f"Campo requerido '{field_name}' no encontrado"

        if "{TEXT}" not in plugin_data.get("prompt", ""):
            return False, "El prompt debe contener {TEXT}"

        # Crear archivo JSON
        custom_dir = self._plugin_dirs[1]
        filename = f"{plugin_data['id']}.json"
        filepath = os.path.join(custom_dir, filename)

        if os.path.exists(filepath):
            return False, f"Ya existe un plugin con el ID: {plugin_data['id']}"

        plugin_data.setdefault("author", "User")
        plugin_data.setdefault("version", "1.0.0")
        plugin_data.setdefault("license", "MIT")
        plugin_data.setdefault("is_builtin", False)
        plugin_data.setdefault("is_enabled", True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(plugin_data, f, indent=2, ensure_ascii=False)

        # Recargar
        self.discover(force=True)

        return True, f"Plugin creado: {filename}"

    def export_plugin(self, template_id: str, export_path: str) -> tuple[bool, str]:
        """Exporta un plugin a un archivo."""
        template = self._templates.get(template_id)
        if not template:
            return False, f"Plugin no encontrado: {template_id}"

        data = template.to_dict()
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True, f"Plugin exportado: {export_path}"

    def get_plugin_dirs(self) -> list[str]:
        """Devuelve la lista de directorios de plugins."""
        return list(self._plugin_dirs)

    def run_template(
        self,
        template_id: str,
        text: str,
        engine,
        progress_callback: Callable | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Ejecuta un template con un motor de adaptación.

        Args:
            template_id: ID del template a ejecutar.
            text: Texto a analizar.
            engine: Motor de adaptación (GeminiAdaptationEngine, etc.).
            progress_callback: Callback de progreso.
            **kwargs: Variables adicionales para el prompt.

        Returns:
            Dict con el resultado o error.
        """
        template = self._templates.get(template_id)
        if not template:
            return {"error": f"Template no encontrado: {template_id}"}

        if not template.meta.is_enabled:
            return {"error": f"Template deshabilitado: {template_id}"}

        # Renderizar prompt
        prompt = template.render_prompt(text, **kwargs)

        # Llamar al motor
        try:
            if progress_callback:
                progress_callback(0, 1, f"Ejecutando {template.meta.name}...")

            # Usar el método _call del motor si está disponible
            if hasattr(engine, "_call"):
                result = engine._call(
                    prompt,
                    template.max_tokens,
                    template.temperature,
                    timeout=120,
                )
            else:
                return {"error": "Motor no compatible con plugins"}

            if "error" in result:
                return {"error": result["error"]}

            return {
                "text": result["text"],
                "template": template.meta.name,
                "template_id": template.meta.id,
                "icon": template.icon,
                "provider": getattr(engine, "PROVIDER", "Unknown"),
                "model": getattr(engine, "model", "unknown"),
                "max_tokens": template.max_tokens,
                "temperature": template.temperature,
            }

        except Exception as e:
            return {"error": f"Error ejecutando template: {e}"}

    def to_compatible_dict(self, template_id: str) -> dict | None:
        """Convierte un plugin al formato compatible con TEMPLATES de GeminiAdaptationEngine."""
        template = self._templates.get(template_id)
        if not template:
            return None

        return {
            "prompt": template.prompt,
            "icon": template.icon,
            "desc": template.desc,
            "max_tokens": template.max_tokens,
            "temperature": template.temperature,
        }


# ── Singleton ────────────────────────────────────────────────────────────────

_manager: PluginManager | None = None


def get_plugin_manager(**kwargs) -> PluginManager:
    """Obtiene el gestor de plugins singleton."""
    global _manager
    if _manager is None:
        _manager = PluginManager(**kwargs)
    return _manager


def reset_plugin_manager():
    """Resetea el gestor de plugins (para tests)."""
    global _manager
    _manager = None
