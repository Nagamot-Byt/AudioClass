# Contribuir a AudioClass

Gracias por tu interés en contribuir a AudioClass. Este documento explica cómo extender la aplicación, particularmente cómo agregar nuevos proveedores de IA usando el sistema de plugins.

---

## Índice

1. [Requisitos previos](#requisitos-previos)
2. [Configuración del entorno](#configuración-del-entorno)
3. [Agregar un proveedor de transcripción](#agregar-un-proveedor-de-transcripción)
4. [Agregar un proveedor de adaptación (análisis con IA)](#agregar-un-proveedor-de-adaptación)
5. [Estructura del proyecto](#estructura-del-proyecto)
6. [Convenciones de código](#convenciones-de-código)
7. [Testing](#testing)
8. [Pull Requests](#pull-requests)
9. [Debugging y problemas comunes](#debugging-y-problemas-comunes)

---

## Requisitos previos

- Python 3.9+
- Conocimiento de Python intermedio
- Una cuenta de API del proveedor que quieras integrar (si es cloud)

## Configuración del entorno

```bash
# Clonar el repositorio
git clone https://github.com/usuario/audioclass.git
cd audioclass

# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements_v91.txt

# Ejecutar tests
python3 test_core_units.py
python3 test_config_migration.py
```

---

## Agregar un proveedor de transcripción

El sistema de plugins está en `ai_providers.py`. Para agregar un nuevo motor de transcripción:

### Paso 1: Crear la clase del motor

Crea un archivo `mi_motor.py` (o agrega en `audioclass_core.py`) con esta interfaz:

```python
class MiMotorTranscripcion:
    """Motor de transcripción personalizado."""

    def __init__(self, api_key: str = "", model: str = "", **kwargs):
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio_path: str, language: str = "es", on_partial=None, on_progress=None, **kwargs) -> str:
        """Transcribe un archivo de audio.

        Args:
            audio_path: Ruta al archivo de audio (WAV/MP3/FLAC).
            language: Código de idioma (ISO 639-1).
            on_partial: Callback opcional para texto parcial (streaming).
            on_progress: Callback opcional (0.0-1.0) para progreso.

        Returns:
            Texto transcrito.
        """
        # Tu implementación aquí
        raise NotImplementedError
```

### Paso 2: Registrar en el sistema de plugins

En `ai_providers.py`, dentro de `create_default_registry()`, agrega:

```python
from mi_motor import MiMotorTranscripcion

registry.register_transcription(
    "mi_motor",
    TranscriptionProvider(
        name="Mi Motor (Descripción corta)",
        key="mi_motor",
        requires_key=True,  # True si necesita API key
        requires_url=False,  # True si necesita URL del servidor
        description="Transcripción con Mi Motor. Descripción para el usuario.",
        config_key_api="mi_motor_api_key",  # Clave en config para la API key
    ),
)
```

### Paso 3: Agregar lazy import del motor (si es cloud)

En `create_default_registry()`, para motores que dependen de librerías pesadas:

```python
def _lazy_mi_motor(**kwargs):
    from mi_motor import MiMotorTranscripcion

    return MiMotorTranscripcion(**kwargs)
```

### Paso 4: Integrar en la UI (opcional)

Para que aparezca en el selector de motores, la UI ya consulta `ProviderRegistry.get_available_transcription_engines(config)`. Si registraste el proveedor con `config_key_api`, la UI automáticamente sabrá si está disponible (tiene API key configurada).

Si necesitas lógica de UI personalizada (ej: campo de URL adicional), consulta la sección [Integración avanzada](#integración-avanzada).

---

## Agregar un proveedor de adaptación

Los proveedores de adaptación generan análisis estructurado de transcripciones (resúmenes, flashcards, exámenes, etc.).

### Paso 1: Crear la clase del motor

```python
class MiMotorAdaptacion:
    """Motor de adaptación (análisis con IA)."""

    def __init__(self, api_key: str = "", model: str = "", **kwargs):
        self.api_key = api_key
        self.model = model

    def adapt(self, text: str, template: str = "resumen", language: str = "es", **kwargs) -> str:
        """Genera un análisis estructurado del texto.

        Args:
            text: Texto transcrito de la clase.
            template: Tipo de análisis (resumen, flashcards, examen, etc.).
            language: Idioma de salida.

        Returns:
            Análisis en formato Markdown.
        """
        raise NotImplementedError
```

### Paso 2: Registrar en el sistema de plugins

```python
from mi_motor_adaptacion import MiMotorAdaptacion


def _lazy_mi_adapt(**kwargs):
    from mi_motor_adaptacion import MiMotorAdaptacion

    return MiMotorAdaptacion(**kwargs)


registry.register_adaptation(
    "mi_proveedor",
    AdaptationProvider(
        name="Mi Proveedor (Descripción)",
        key="mi_proveedor",
        requires_key=True,
        description="Análisis con Mi Proveedor. Gratis con plan inicial.",
        config_key_api="mi_proveedor_api_key",
        config_key_model="mi_proveedor_model",
        models={  # alias -> model_id
            "rapido": "mi-model-rapido",
            "calidad": "mi-model-calidad",
        },
        engine_class=_lazy_mi_adapt,
    ),
)
```

### Paso 3: Agregar template personalizado (opcional)

Los templates de análisis están definidos en `audioclass_core.py` como `ADAPTATION_TEMPLATES`. Para agregar uno nuevo:

```python
ADAPTATION_TEMPLATES = {
    # ... templates existentes ...
    "mi_template": {
        "label": "Mi Análisis Personalizado",
        "prompt": "Genera un análisis que incluya: ...",
    },
}
```

---

## Estructura del proyecto

```
audioclass_v91.py          # App GUI principal (migrando lógica a módulos)
├── audioclass_core.py     # Motor puro: pipeline, transcripción, adaptación
├── ai_providers.py        # Sistema de plugins (registry extensible)
├── ui_builder.py          # Builder functions de UI
├── config_manager.py      # Config persistente + migraciones
├── theme.py               # Paletas WCAG AA
├── recording_engine.py    # Mixin de grabación
├── mic_optimizer_ui.py    # Mixin de optimización de micrófono
├── transcription_engines.py # Registro legacy de motores
├── export_utils.py        # Helpers PDF/DOCX
├── update_checker.py      # Verificador de actualizaciones
├── audio_quality_checker.py # Verificador de calidad
├── sound_error_solver.py  # Corrección automática de audio
├── run_ci_suite.py        # Suite de tests E2E
├── test_core_units.py     # Unit tests del core
├── test_config_migration.py # Tests de migración de config
└── test_colab_server_security.py # Tests de seguridad
```

---

## Convenciones de código

- **Type hints** en nuevos módulos y funciones públicas
- **Docstrings** en formato Google para funciones públicas
- **Naming**: `snake_case` para funciones/variables, `PascalCase` para clases
- **Lazy imports** para dependencias pesadas (whisper, torch, etc.)
- **Callbacks**: usar `on_partial` para streaming, `on_progress` para progreso
- **Paleta de colores**: usar `self._C` (propiedad que retorna la paleta activa) en vez de colores hardcodeados

---

## Testing

### Ejecutar todos los tests

```bash
python3 test_core_units.py          # 25 tests unitarios del core
python3 test_config_migration.py    # 40 tests de migración de config
python3 test_colab_server_security.py # 11 tests de seguridad del servidor
```

### Escribir tests para tu nuevo motor

```python
import unittest


class TestMiMotorTranscripcion(unittest.TestCase):
    def test_basic_transcription(self):
        """Test que el motor transcribe audio básico."""
        from mi_motor import MiMotorTranscripcion

        engine = MiMotorTranscripcion(api_key="test-key")
        # Test con audio sintético o mock
        result = engine.transcribe("test_audio.wav")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_requires_api_key(self):
        """Test que el motor requiere API key."""
        from mi_motor import MiMotorTranscripcion

        with self.assertRaises(ValueError):
            MiMotorTranscripcion(api_key="")

    def test_plugin_registration(self):
        """Test que el motor se registra correctamente."""
        from ai_providers import create_default_registry

        registry = create_default_registry()
        # Verificar que tu motor está registrado
        self.assertIn("mi_motor", registry.get_all_transcription())


if __name__ == "__main__":
    unittest.main()
```

### Integrar en la suite de tests

Edita `test_core_units.py` para importar y ejecutar tus tests:

```python
from test_mi_motor import TestMiMotorTranscripcion

# Agregar al suite principal
all_tests.addTest(unittest.makeSuite(TestMiMotorTranscripcion))
```

---

## Pull Requests

### Checklist antes de enviar

- [ ] Tu código compila sin errores: `python3 -m py_compile mi_motor.py`
- [ ] Tests pasan: `python3 test_core_units.py`
- [ ] Agregaste tests para tu nuevo motor
- [ ] Documentaste tu motor en `TERCEROS_Y_LICENCIAS.md` si agregas dependencias
- [ ] Type hints en funciones públicas
- [ ] Docstrings en funciones públicas
- [ ] Lazy imports si tu motor depende de librerías pesadas

### Formato del PR

```
[Tipo] Descripción breve

- Detalle 1
- Detalle 2

Tipos: [feat], [fix], [docs], [test], [refactor]
```

Ejemplo:

```
[feat] Agregar soporte para Deepgram como proveedor de transcripción

- Nuevo motor DeepgramTranscription con streaming en tiempo real
- Registrado en ProviderRegistry con config_key_api="deepgram_api_key"
- Tests unitarios incluidos
- Documentación actualizada
```

---

## Integración avanzada

### Campo de URL personalizado

Si tu motor necesita una URL (ej: servidor Colab), usa `config_key_url`:

```python
registry.register_transcription(
    "mi_motor",
    TranscriptionProvider(
        name="Mi Motor",
        key="mi_motor",
        requires_url=True,
        config_key_url="mi_motor_url",
    ),
)
```

### Modelos múltiples

Si tu proveedor soporta varios modelos, usa `config_key_model` y `models`:

```python
registry.register_adaptation(
    "mi_proveedor",
    AdaptationProvider(
        name="Mi Proveedor",
        key="mi_proveedor",
        config_key_model="mi_proveedor_model",
        models={
            "rapido": "model-1",
            "calidad": "model-2",
        },
    ),
)
```

La UI mostrará un selector con los aliases ("rapido", "calidad") y mapeará al model_id real.

### Hooks de UI personalizados

Si necesitas lógica de UI específica (ej: campo de configuración adicional), consulta `ui_builder.py` y `audioclass_v91.py` para entender el patrón de builder functions. Cada builder retorna un diccionario de widgets que se integra en el layout principal.

---

## Debugging y problemas comunes

### Errores de importación

**Problema**: `ModuleNotFoundError: No module named 'audioclass_core'`

```bash
# Solución: Ejecutar desde la raíz del proyecto
python3 -m py_compile audioclass_core.py  # Verifica que compila solo
python3 -c "from audioclass_core import AudioPipeline"  # Verifica importación
```

**Problema**: `ImportError: cannot import name 'X' from 'Y'`

```bash
# Verificar qué exporta el módulo
python3 -c "import audioclass_core; print(dir(audioclass_core))"
# Verificar si el nombre existe
python3 -c "from audioclass_core import MiClase; print('OK')"
```

**Problema**: Circular import entre `audioclass_v91.py` y `audioclass_core.py`

```bash
# Solución: Usar lazy imports en funciones, no a nivel de módulo
# ❌ Mal
from audioclass_core import AudioPipeline  # Al inicio del archivo

# ✅ Bien
def mi_funcion():
    from audioclass_core import AudioPipeline  # Dentro de la función
    pipeline = AudioPipeline()
```

---

### UI y customtkinter

**Problema**: `TclError: can't invoke "wm" command` o UI no carga

```bash
# Verificar customtkinter instalado
pip show customtkinter
# Reinstalar si está corrupto
pip install --force-reinstall customtkinter
```

**Problema**: `Segmentation fault` al iniciar en Linux

```bash
# Verificar display disponible
echo $DISPLAY
# Si no hay display, usar xvfb
xvfb-run python3 audioclass_v91.py
```

**Problema**: Colores no se aplican o UI se ve rara

```python
# Verificar paleta activa
from theme import PALETTES

print(PALETTES["dark"].keys())  # Debe tener 18 claves

# Verificar que se usa la paleta, no colores hardcodeados
# ❌ Mal
label.configure(text_color="#FFFFFF")

# ✅ Bien
label.configure(text_color=self._C["fg"])
```

---

### Audio y grabación

**Problema**: `sounddevice.PortAudioError` o no detecta micrófono

```bash
# Verificar dispositivos de audio
python3 -c "import sounddevice; print(sounddevice.query_devices())"

# Verificar PortAudio instalado
python3 -c "import sounddevice; print(sounddevice.__version__)"

# Linux: instalar dependencias del sistema
sudo apt-get install portaudio19-dev python3-dev
```

**Problema**: `noisereduce` lento o falla

```bash
# Verificar numpy version (noisereduce es sensible a esto)
pip show numpy  # Debe ser 1.24+

# Probar con audio sintético
python3 -c "
import numpy as np
import noisereduce as nr
audio = np.random.randn(16000).astype(np.float32)
result = nr.reduce_noise(y=audio, sr=16000)
print('OK', result.shape)
"
```

**Problema**: Audio corrupto o silencioso después de procesamiento

```python
# Verificar que el pipeline procesa correctamente
from audioclass_core import AudioPipeline
import numpy as np

pipeline = AudioPipeline(profile="universidad")
audio = np.random.randn(16000).astype(np.float32)  # 1s de ruido
result = pipeline.process(audio, sr=16000)

print(f"Input: {audio.shape}, Output: {result.shape}")
print(f"Input RMS: {np.sqrt(np.mean(audio**2)):.4f}")
print(f"Output RMS: {np.sqrt(np.mean(result**2)):.4f}")
```

---

### Whisper y transcripción

**Problema**: Modelo no descarga o falla al cargar

```bash
# Verificar conexión a internet
curl -I https://huggingface.co

# Verificar cache de modelos
ls -la ~/.cache/huggingface/hub/  # Linux/macOS
ls -la ~/Library/Caches/huggingface/hub/  # macOS

# Limpiar cache corrupto
rm -rf ~/.cache/huggingface/hub/models--Systran--faster-whisper-*
```

**Problema**: `CUDA out of memory` o modelo muy grande

```python
# Verificar GPU disponible
import torch

print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")

# Usar modelo más pequeño
config["whisper_model"] = "tiny"  # En vez de 'large'
config["whisper_compute"] = "int8"  # En vez de 'float16'
```

**Problema**: Transcripción lenta en CPU

```python
# Verificar que faster-whisper usa CPU optimizado
from audioclass_core import LocalWhisperEngine

engine = LocalWhisperEngine(model_size="tiny", device="cpu")

# Usar modo rápido (skips some processing)
result = engine.transcribe("audio.wav", fast_mode=True)
```

---

### API keys y configuración

**Problema**: API key no se guarda o se pierde

```python
# Verificar config manager
from config_manager import load_config, save_config

config = load_config()
print(f"gemini_api_key: {bool(config.get('gemini_api_key'))}")

# Forzar guardado
config["gemini_api_key"] = "tu-key-aqui"
save_config(config)

# Verificar que persiste
config2 = load_config()
assert config2.get("gemini_api_key") == "tu-key-aqui"
```

**Problema**: Config corrupta o incompatible

```bash
# Verificar archivo de config
ls -la ~/.audioclass/config.json  # Linux/macOS
ls -la %APPDATA%/AudioClass/config.json  # Windows

# Inspeccionar contenido
cat ~/.audioclass/config.json | python3 -m json.tool

# Resetear config (¡borra configuración del usuario!)
rm ~/.audioclass/config.json
# La app creará una nueva con defaults en el próximo arranque
```

**Problema**: Migración de config falla

```python
# Verificar versión de schema
from config_manager import CONFIG_VERSION

print(f"Versión actual: {CONFIG_VERSION}")  # Debe ser 5

# Ejecutar migración manualmente
from config_manager import migrate_config

config = {"theme": "Dark", "whisper_model": "gemini-1.5-flash"}
migrated = migrate_config(config)
print(f"theme: {migrated['theme']}")  # Debe ser 'dark'
print(f"whisper_model: {migrated['whisper_model']}")  # Debe ser 'flash'
```

---

### Hilos y concurrencia

**Problema**: `TclError: can't invoke "configure" command during shutdown`

```python
# Solución: Verificar que el widget existe antes de actualizar
if hasattr(widget, "winfo_exists") and widget.winfo_exists():
    widget.configure(text="nuevo texto")


# O usar el patrón de AudioClass
def _safe_update(self, widget, **kwargs):
    try:
        if widget.winfo_exists():
            widget.configure(**kwargs)
    except Exception:
        pass  # Widget destruido, ignorar
```

**Problema**: UI se congela durante transcripción

```python
# Solución: Ejecutar en hilo separado
import threading


def mi_transcripcion():
    def _worker():
        result = engine.transcribe("audio.wav")
        self.q.put(("transcription_done", result))

    threading.Thread(target=_worker, daemon=True).start()
    # UI no se bloquea
```

**Problema**: `queue.Empty` o mensajes perdidos

```python
# Verificar que _poll() está ejecutándose
# El loop principal debe tener:
self._poll()  # Llamado cada 50ms

# Verificar cola
print(f"Mensajes en cola: {self.q.qsize()}")
```

---

### Linux específico

**Problema**: `SIGABRT` al cerrar la app

```python
# Solución: Usar os._exit() en Linux
import sys

if sys.platform == "linux":
    import os

    os._exit(0)  # Evita SIGABRT de libtorch
```

**Problema**: `GLIBC` version incompatible

```bash
# Verificar versión de glibc
ldd --version

# Solución: Usar Docker o AppImage
python3 -m audioclass.docker_build  # Genera Dockerfile
```

**Problema**: No abre en Wayland

```bash
# Forzar X11
export GDK_BACKEND=x11
python3 audioclass_v91.py
```

---

### macOS específico

**Problema**: `audio_sounddevice` no detecta micrófono

```bash
# Verificar permisos de micrófono
# System Preferences > Security & Privacy > Privacy > Microphone
# Añadir Terminal o Python

# Verificar dispositivos
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

**Problema**: App no firma o bloqueada por Gatekeeper

```bash
# Para desarrollo, desbloquear manualmente
xattr -cr /path/to/AudioClass.app

# Para distribución, firmar con certificado
codesign --force --deep --sign "Developer ID Application" AudioClass.app
```

---

### PyInstaller y distribución

**Problema**: Build falla con `ModuleNotFoundError`

```bash
# Verificar spec file
cat audioclass.spec

# Agregar módulo faltante al spec
collected = collect_all('mi_modulo')

# Ejecutar build
pyinstaller audioclass.spec --clean
```

**Problema**: EXE muy grande (>200MB)

```bash
# Ver qué se está empaquetando
pyi-archive_viewer -l dist/audioclass/audioclass

# Excluir módulos innecesarios en spec
excludes=['tkinter', 'matplotlib', 'scipy', 'pandas']
```

**Problema**: EXE no ejecuta en otra máquina

```bash
# Verificar dependencias dinámicas (Linux)
ldd dist/audioclass/audioclass | grep "not found"

# Verificar que usa onedir, no onefile
ls dist/audioclass/
```

---

### Herramientas de debugging

**Logging detallado**

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# O en la app, habilitar verbose mode
python3 audioclass_v91.py --verbose
```

**Inspección de config**

```python
from config_manager import load_config

config = load_config()
for k, v in sorted(config.items()):
    print(f"{k}: {v}")
```

**Profiling de rendimiento**

```python
import cProfile
import pstats

# Profilear una función
cProfile.run("mi_funcion()", "profile_output")
stats = pstats.Stats("profile_output")
stats.sort_stats("cumulative")
stats.print_stats(10)  # Top 10 funciones más lentas
```

**Debug de hilos**

```python
import threading

# Ver todos los hilos activos
for thread in threading.enumerate():
    print(f"{thread.name}: {thread.is_alive()}")

# Verificar si el hilo principal está bloqueado
import signal


def handler(sig, frame):
    import traceback

    traceback.print_stack(frame)
    signal.signal(signal.SIGUSR1, handler)


signal.signal(signal.SIGUSR1, handler)
# Enviar kill -USR1 <pid> para ver stack trace
```

---

## Preguntas

Si tienes preguntas, abre un issue en GitHub con el tag `[question]`.

Gracias por contribuir a AudioClass.
