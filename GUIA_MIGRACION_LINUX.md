# AudioClass - Guia de Migracion a Linux

> **Fecha**: 2026-08-21
> **Estado**: Windows -> Linux
> **Repo**: https://github.com/Nagamot-Byt/AudioClass

---

## 1. Clonar el repo

```bash
git clone https://github.com/Nagamot-Byt/AudioClass.git
cd AudioClass
```

---

## 2. Dependencias del sistema (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y \
    python3 python3-pip python3-venv \
    libportaudio2 libsndfile1 \
    libgl1-mesa-glx libglib2.0-0 \
    xvfb \
    portaudio19-dev \
    build-essential \
    git curl wget
```

Para Fedora/RHEL:
```bash
sudo dnf install -y \
    python3 python3-pip \
    portaudio-devel libsndfile \
    mesa-libGL glib2 \
    xorg-x11-server-Xvfb \
    gcc gcc-c++ make \
    git curl wget
```

---

## 3. Instalacion rapida (un solo comando)

```bash
chmod +x quick_start.sh
./quick_start.sh
```

Esto:
1. Crea un entorno virtual en `venv/`
2. Instala libportaudio2 y libsndfile1 (si falta)
3. Instala todas las dependencias de `requirements_v91.txt`
4. Lanza la app

---

## 4. Instalacion manual paso a paso

```bash
# Crear venv
python3 -m venv venv
source venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias
pip install -r requirements_v91.txt

# Instalar PyInstaller (para compilar)
pip install pyinstaller

# Lanzar la app
python audioclass_v91.py
```

---

## 5. Ejecutar la suite de tests

```bash
# Suite completa (16+ tests)
python run_ci_suite.py

# Test individual
python test_ui_smoke.py
python test_privacy_consent.py
python test_wcag_contrast.py
python test_config_manager.py
python test_api_integration.py
python test_mic_detection.py
python test_audio_quality_solver.py
python test_quality_gate_e2e.py

# E2E headless (requiere xvfb en Linux sin display)
xvfb-run -a python audioclass_v91.py --e2e-ui wizard
xvfb-run -a python audioclass_v91.py --e2e-ui config
xvfb-run -a python audioclass_v91.py --e2e-ui widgets
xvfb-run -a python audioclass_v91.py --e2e-ui mic
```

---

## 6. Compilar para Linux

### Opcion recomendada: onedir (carpeta, rapido)
```bash
bash build_linux.sh --onedir
# Genera: dist/AudioClass/ (carpeta ~55MB)
# Para distribuir: comprimir toda la carpeta
```

### Opcion: onefile (exe unico, ~3GB en Linux)
```bash
bash build_linux.sh --onefile
# Genera: dist/AudioClass.exe (~3GB)
# Nota: PyInstaller en Linux produce binarios grandes por torch+ctranslate2
```

### Opcion: AppImage (portable, sin instalar)
```bash
bash build_appimage.sh
# Genera: dist/AudioClass-x86_64.AppImage
```

---

## 7. Modelos de transcripcion

Los modelos se descargan automaticamente la primera vez que ejecutas la app.

Ubicacion en Linux: `~/.cache/whisper/` y `~/.cache/huggingface/`

Para pre-cargarlos manualmente:
```bash
# Whisper tiny (para transcripcion local)
python -c "
import whisper
whisper.load_model('tiny')
print('Modelo tiny descargado')
"

# faster-whisper CT2 tiny+base
python -c "
from huggingface_hub import snapshot_download
for name in ('tiny', 'base'):
    snapshot_download(f'Systran/faster-whisper-{name}', local_dir=f'models_ct2/{name}')
    print(f'Modelo CT2 {name} descargado')
"
```

---

## 8. Estructura del proyecto en Linux

```
AudioClass/
  audioclass_v91.py           # App principal (GUI)
  audioclass_core.py          # Nucleo de audio/DSP
  audio_quality_checker.py    # Verificador de calidad de audio
  sound_error_solver.py       # Solucionador de problemas de audio

  # Modulos extraidos
  ui_builder.py               # Construccion de UI
  config_manager.py           # Config persistente
  theme.py                    # Tema y paletas WCAG
  recording_engine.py         # Motor de grabacion
  transcription_engines.py    # Registro de motores
  export_utils.py             # Helpers PDF/DOCX

  # Assets
  assets/
    audioclass_theme.json     # Tema CTk
    DejaVuSans.ttf            # Fuentes para PDF

  # Modelos (se descargan automaticamente)
  models_ct2/tiny/            # Modelo Whisper tiny (CT2)
  models_ct2/base/            # Modelo Whisper base (CT2)

  # Tests
  run_ci_suite.py             # Suite de tests
  test_*.py                   # Tests individuales (32 archivos)

  # Build
  build_linux.sh              # Build Linux
  build_appimage.sh           # Build AppImage
  AudioClass_v91_linux.spec   # Spec PyInstaller Linux onedir
  AudioClass_v91_onefile_linux.spec  # Spec PyInstaller Linux onefile

  # CI/CD
  .github/workflows/
    ci.yml                    # CI (ubuntu)
    release.yml               # Release (3 plataformas)
```

---

## 9. Diferencias Windows vs Linux

| Aspecto | Windows | Linux |
|---|---|---|
| Python | `python` o `py` | `python3` |
| venv activation | `venv\Scripts\activate` | `source venv/bin/activate` |
| Dependencias audio | portaudio incluido | `sudo apt install libportaudio2` |
| Exe PyInstaller | ~570 MB onefile | ~3 GB onefile (torch grande) |
| Exe PyInstaller | 55 MB onedir | 55 MB onedir |
| Microfono | WASAPI/DirectSound | ALSA/PulseAudio |
| GUI display | nativo | xvfb para CI/headless |
| Permisos | admin para driver | group `audio` |
| Servicios audio | Windows Audio | PulseAudio/PipeWire |

---

## 10. Guia Completa de Debugging

### 10.1 Errores de dependencias y imports

#### "No module named 'sounddevice'"
**Causa**: Falta la libreria portaudio del sistema.
```bash
# Ubuntu/Debian
sudo apt install libportaudio2 portaudio19-dev
pip install sounddevice

# Fedora
sudo dnf install portaudio-devel
pip install sounddevice

# Arch
sudo pacman -S portaudio
pip install sounddevice
```

#### "No module named '_tkinter'"
**Causa**: Python no incluye tkinter (comun en instalaciones minimalistas).
```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

#### "No module named 'customtkinter'"
**Causa**: Falta customtkinter en el venv.
```bash
pip install customtkinter==6.0.0
```

#### "ModuleNotFoundError: No module named 'PyInstaller'"
```bash
pip install pyinstaller==6.21.0
```

#### "ImportError: libGL.so.1: cannot open shared object file"
**Causa**: Falta la libreria de OpenGL (necesaria para matplotlib/imshow).
```bash
sudo apt install libgl1-mesa-glx libglib2.0-0
# o
export PYOPengl_silent=1  # desactivar warnings
```

---

### 10.2 Errores de audio y microfono

#### "PortAudioLibraryNotInitialized" o "Illegal instruction"
**Causa**: Portaudio no esta inicializado o hay conflicto de versiones.
```bash
# Reinstalar portaudio
sudo apt remove libportaudio2
sudo apt install libportaudio2 portaudio19-dev
pip install --force-reinstall sounddevice

# Verificar que funciona
python -c "import sounddevice as sd; print(sd.query_devices())"
```

#### "Permission denied: /dev/snd/*"
**Causa**: El usuario no tiene permisos de audio.
```bash
# Agregar al grupo audio
sudo usermod -aG audio $USER

# Cerrar sesion y volver a entrar, o:
newgrp audio

# Verificar
groups  # debe incluir 'audio'
```

#### "AudioHardware: altohal_..." o "ALSA lib pcm.c:..."
**Causa**: ALSA no encuentra el dispositivo o hay conflicto con PulseAudio.
```bash
# Verificar dispositivos disponibles
python -c "import sounddevice as sd; print(sd.query_devices())"

# Forzar uso de PulseAudio
export PULSE_AUDIO_DEVICE=alsa_output.pci-0000_00_1f.3.analog-stereo.monitor

# Desactivar mensajes ALSA (cosmetico)
export ALSA_CONFIG_TOML=/etc/asound.conf  # o crear uno silencioso
```

#### " OSError: [Errno -9996] Invalid device (or similar)"
**Causa**: El dispositivo de audio no existe o esta ocupado.
```bash
# Listar todos los dispositivos
python -c "import sounddevice as sd; print(sd.query_devices())"

# Probar con un dispositivo especifico
python -c "import sounddevice as sd; print(sd.query_devices(kind='input'))"

# Verificar que PulseAudio/PipeWire esta corriendo
pulseaudio --check && echo 'PulseAudio running' || echo 'PulseAudio NOT running'
pactl list sources short
```

#### Microfono captura silencio (p90 < 0.005)
**Causa**: Permisos, mute, nivel en 0, o driver desactualizado.
```bash
# 1. Verificar nivel en PulseAudio
pactl list sources | grep -A5 'RUNNING\|SUSPENDED'

# 2. Ajustar nivel de captura
pactl set-source-volume @DEFAULT_SOURCE@ 100%

# 3. Desmutear
pactl set-source-mute @DEFAULT_SOURCE@ 0

# 4. Ejecutar diagnostico
python diagnostico_mic.py

# 5. En la app: Configuracion > Auto-detectar microfono
```

#### "ALSA lib pcm.c:857:(snd_pcm_open) Unknown PCM default"
**Causa**: No hay dispositivo de audio configurado.
```bash
# Crear configuracion ALSA basica
cat > ~/.asoundrc << 'EOF'
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
EOF

# Reiniciar PulseAudio
pulseaudio -k
pulseaudio --start
```

---

### 10.3 Errores de GUI y display

#### "cannot open display" o "No display"
**Causa**: No hay servidor X (comun en SSH, CI, o servidores).
```bash
# Solucion 1: xvfb (virtual display)
sudo apt install xvfb
xvfb-run -a python audioclass_v91.py

# Solucion 2: iniciar Xvfb manualmente
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
python audioclass_v91.py

# Solucion 3: en CI (GitHub Actions)
# xvfb-run ya esta en el workflow ci.yml
```

#### "Segmentation fault" al abrir la GUI
**Causa**: Conflicto de versiones de tkinter o customtkinter.
```bash
# Reinstalar tkinter
gpip uninstall customtkinter
gpip install customtkinter==6.0.0

# Verificar version de tkinter
python -c "import tkinter; print(tkinter.TkVersion)"

# Si TkVersion < 8.6, actualizar Python
sudo apt install python3.12 python3.12-tk
```

#### Ventana se abre pero no se ve (display remoto)
```bash
# Usar VNC o X11 forwarding
ssh -X usuario@servidor  # X11 forwarding

# O usar VNC
sudo apt install x11vnc
x11vnc -display :99 -forever -nopw &
```

#### "Font not found" o caracteres raros en PDF
**Causa**: Faltan las fuentes DejaVu para PDF.
```bash
# Verificar que las fuentes estan en assets/
ls -la assets/DejaVuSans*.ttf

# Si no estan, copiar del sistema
cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf assets/
cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf assets/
```

---

### 10.4 Errores de PyInstaller (build)

#### "PyInstaller.toc not found" o build falla
```bash
# Limpiar cache completamente
rm -rf build/ dist/ *.spec.bak

# Recompilar con cache limpio
pyinstaller --clean AudioClass_v91_linux.spec --noconfirm
```

#### "ModuleNotFoundError" despues de compilar
**Causa**: PyInstaller no detecta un import dinamico.
```bash
# Agregar al hiddenimports en el spec
# Editar AudioClass_v91_linux.spec:
#   hiddenimports=['mi_modulo', ...]

# O usar --collect-all
pyinstaller --collect-all mi_modulo AudioClass_v91_linux.spec
```

#### Exe muito grande (>3GB onefile en Linux)
**Causa**: PyInstaller empaqueta torch + ctranslate2 completo.
```bash
# Usar onedir en vez de onefile (recomendado)
bash build_linux.sh --onedir
# Resultado: dist/AudioClass/ (~55MB)

# O usar AppImage (portable, sin instalar)
bash build_appimage.sh
```

#### "ELF header" o "cannot execute binary"
**Causa**: El exe fue compilado para otra arquitectura.
```bash
# Verificar arquitectura
file dist/AudioClass/AudioClass
# Debe mostrar: ELF 64-bit LSB executable, x86-64

# Recompilar en la arquitectura correcta
bash build_linux.sh --onedir
```

---

### 10.5 Errores de modelos y transcripcion

#### "No module named 'faster_whisper'" o "No module named 'ctranslate2'"
```bash
# Instalar dependencias de transcripcion
pip install faster-whisper==1.2.1 ctranslate2

# Para CPU (sin GPU)
pip install torch==2.13.0+cpu --index-url https://download.pytorch.org/whl/cpu
```

#### "FileNotFoundError: models_ct2/tiny/model.bin"
**Causa**: Los modelos no se descargaron.
```bash
# Descargar modelos CT2
python -c "
from huggingface_hub import snapshot_download
for name in ('tiny', 'base'):
    snapshot_download(f'Systran/faster-whisper-{name}', local_dir=f'models_ct2/{name}')
    print(f'Modelo {name} descargado')
"

# Verificar
ls -la models_ct2/tiny/model.bin
```

#### "CUDA out of memory" (si tienes GPU)
**Causa**: La GPU no tiene suficiente VRAM.
```bash
# Forzar CPU
export CUDA_VISIBLE_DEVICES=""
python audioclass_v91.py

# O reducir el tamano del modelo
# En la app: Configuracion > Modelo > tiny (en vez de base)
```

#### Transcripcion devuelve "Transcribe faithfully" o basura
**Causa**: Audio de muy baja calidad o silencio.
```bash
# 1. Verificar calidad del audio grabado
python -c "
from audio_quality_checker import check_wav_file
report = check_wav_file('grabacion.wav')
print(f'Verdicto: {report.verdict}')
print(f'RMS: {report.rms:.4f}')
print(f'p90: {report.p90:.4f}')
"

# 2. Si es silencio: revisar microfono (seccion 10.2)
# 3. Si es debil: usar boost de ganancia en Configuracion
```

---


### 10.6 Errores de red y API

#### "google.auth.exceptions.TransportError"
**Causa**: No hay conexion a internet o proxy bloquea.
```bash
# Verificar conexion
curl -I https://generativelanguage.googleapis.com

# Si usas proxy
export HTTPS_PROXY=http://proxy:8080
export HTTP_PROXY=http://proxy:8080

# Verificar que la API key es valida
python -c "
import os
key = os.environ.get('GEMINI_API_KEY', '')
print(f'API Key configurada: {bool(key)}')
print(f'Longitud: {len(key)}')
"
```

#### "403 Forbidden" o "401 Unauthorized"
**Causa**: API key invalida o expirada.
```bash
# Verificar la key en Configuracion > API Key
# Generar nueva key en:
#   Gemini: https://aistudio.google.com/apikey
#   OpenAI: https://platform.openai.com/api-keys
```

#### "Rate limit exceeded" (429)
**Causa**: Demasiadas peticiones a la API.
```bash
# Esperar 60 segundos y reintentar
# O usar transcripcion local (sin API)
python audioclass_v91.py
# En la app: Configuracion > Motor > Local (faster-whisper)
```

---

### 10.7 Errores de permisos y archivos

#### "Permission denied: [Errno 13]"
```bash
# Verificar permisos de la carpeta
dpwd -la AudioClass/

# Corregir permisos
chmod -R u+rw AudioClass/

# Si es un problema de venv
rm -rf venv/
python3 -m venv venv
source venv/bin/activate
```

#### "No space left on device"
```bash
# Verificar espacio
df -h /

# Limpiar cache de pip
pip cache purge
rm -rf ~/.cache/pip

# Limpiar builds antiguos
rm -rf build/ dist/

# Limpiar cache de modelos (cuidado: re-descarga)
rm -rf ~/.cache/whisper/
rm -rf ~/.cache/huggingface/
```

---

### 10.8 Errores de CI/CD

#### CI falla en ubuntu pero funciona local
**Causa**: Diferencias entre el runner de GitHub y tu maquina.
```bash
# 1. Clonar en limpio para reproducir
rm -rf /tmp/ac_test
git clone . /tmp/ac_test
cd /tmp/ac_test

# 2. Instalar dependencias exactas
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_v91.txt

# 3. Ejecutar la suite
python run_ci_suite.py

# 4. Verificar que xvfb funciona
xvfb-run -a python test_ui_smoke.py
```

#### "timeout" en tests E2E
**Causa**: La app tarda mas de lo esperado en CI.
```bash
# Aumentar timeout en el workflow
# Editar .github/workflows/ci.yml:
#   timeout-minutes: 30  (en vez de 15)

# O ejecutar test individual con timeout mayor
timeout 300 python test_e2e_ui.py
```

---

### 10.9 Comandos de diagnostico rapido

```bash
# Verificar entorno completo
python -c "
import sys, platform, os
print(f'Python: {sys.version}')
print(f'Plataforma: {platform.platform()}')
print(f'CWD: {os.getcwd()}')
print(f'User: {os.getenv(\"USER\", \"?\")}')
print()
# Dependencias criticas
for mod in ['sounddevice', 'numpy', 'scipy', 'customtkinter',
            'faster_whisper', 'torch', 'fpdf2', 'PIL']:
    try:
        m = __import__(mod)
        v = getattr(m, '__version__', getattr(m, 'VERSION', '?'))
        print(f'  {mod}: {v}')
    except ImportError:
        print(f'  {mod}: FALTA')
print()
# Audio
devices = __import__('sounddevice').query_devices()
print(f'Dispositivos de audio: {len(devices)}')
"

# Verificar audio
echo "=== Dispositivos de audio ===" && \
python -c "import sounddevice as sd; print(sd.query_devices())" && \
echo "=== PulseAudio ===" && \
pactl info 2>/dev/null | head -5 || echo "PulseAudio no disponible"

# Verificar espacio y permisos
echo "=== Espacio ===" && df -h . && \
echo "=== Permisos ===" && ls -la *.py | head -5

# Verificar modelos
echo "=== Modelos ===" && \
ls -la models_ct2/tiny/ 2>/dev/null || echo "Modelos no descargados" && \
ls -la models_ct2/base/ 2>/dev/null || echo "Base no disponible"
```

---

## 11. Ejecutar con Docker (sin instalar nada)

Si no quieres instalar dependencias en tu sistema, usa Docker.

### 11.1 Construir la imagen
```bash
git clone https://github.com/Nagamot-Byt/AudioClass.git
cd AudioClass

docker build -t audioclass:v9.1 .
```

### 11.2 Ejecutar (sin audio real)
```bash
docker run -it --rm \
  -e DISPLAY=:99 \
  -v audioclass_config:/root/.config/audioclass \
  -v audioclass_recordings:/root/AudioClass_Recordings \
  audioclass:v9.1
```

### 11.3 Ejecutar con microfono real
```bash
# Linux: acceder al microfono del host
docker run -it --rm \
  --device /dev/snd \
  --group-add audio \
  -e PULSE_SERVER=unix:/run/user/$(id -u)/pulse/native \
  -v /run/user/$(id -u)/pulse:/run/user/$(id -u)/pulse \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v audioclass_config:/root/.config/audioclass \
  -v audioclass_recordings:/root/AudioClass_Recordings \
  audioclass:v9.1
```

### 11.4 Usar docker-compose
```bash
# Ejecutar con audio virtual
docker-compose up

# Con microfono real
docker-compose -f docker-compose.yml -f docker-compose.mic.yml up

# Con API keys
gemini_api_key=TU_KEY docker-compose up
openai_api_key=TU_KEY docker-compose up
```

### 11.5 Archivos Docker creados

| Archivo | Funcion |
|---|---|
| `Dockerfile` | Imagen multi-stage con todas las dependencias |
| `docker-compose.yml` | Orquestacion basica (GUI + audio virtual) |
| `docker-compose.mic.yml` | Override para microfono real del host |
| `docker_entrypoint.sh` | Inicia Xvfb + PulseAudio antes de la app |
| `.dockerignore` | Excluye tests y artifacts del build |

### 11.6 Comandos utiles de Docker
```bash
# Ver logs
docker logs audioclass

# Entrar al contenedor
docker exec -it audioclass bash

# Copiar grabaciones del contenedor al host
docker cp audioclass:/root/AudioClass_Recordings ./grabaciones

# Detener todo
docker-compose down

# Limpiar imagenes
docker rmi audioclass:v9.1
```

---

## 12. CI/CD en Linux

El workflow `ci.yml` ya corre en ubuntu. Para verificar:

```bash
# Simular el CI localmente
xvfb-run -a python run_ci_suite.py
```

Para compilar el exe de Linux en CI, el workflow `release.yml` maneja:
- Windows (GitHub runner windows-latest)
- Linux (GitHub runner ubuntu-latest)
- macOS (GitHub runner macos-latest)

---

## 13. Comandos rapidos de referencia

```bash
# Iniciar desde cero
git clone https://github.com/Nagamot-Byt/AudioClass.git && cd AudioClass && bash quick_start.sh

# Ejecutar tests
python run_ci_suite.py

# Compilar Linux
bash build_linux.sh --onedir

# Verificar calidad de audio
python diagnostico_mic.py

# Limpiar build
rm -rf build/ dist/ *.spec.bak
```

---

## 14. Notas para el asistente AI (Buffy/Codebuff)

Cuando retomes este proyecto en Linux, busca:
- `GUIA_PROYECTO.md` para la estructura completa
- `GUIA_MIGRACION_LINUX.md` (este archivo) para instrucciones Linux
- `requirements_v91.txt` para dependencias pinned
- `run_ci_suite.py` para la suite de tests
- `build_linux.sh` para compilar
- `.github/workflows/ci.yml` y `release.yml` para CI/CD

El proyecto esta en `origin/main` con tag `v9.2`.
Commits recientes:
- `3a0be3b` fix(pyinstaller): move QA imports out of try/except
- `83fac1d` test(exe): verify modules in bundled exe
- `08b1116` test(audio): E2E quality gate
- `eaa9b8a` feat(audio): anti-fallo de calidad
- `a1b82fd` test(mic): add test_mic_detection
