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

## 10. Solucion de problemas comunes

### "No module named 'sounddevice'"
```bash
sudo apt install libportaudio2 portaudio19-dev
pip install sounddevice
```

### "No module named '_tkinter'"
```bash
sudo apt install python3-tk
```

### "Cannot open display" (en CI o SSH)
```bash
xvfb-run -a python audioclass_v91.py
# o export DISPLAY=:99 && Xvfb :99 &
```

### "Permission denied: /dev/snd/*"
```bash
sudo usermod -aG audio $USER
# Cerrar sesion y volver a entrar
```

### PyInstaller tarda mucho en Linux
```bash
# Usar onedir en vez de onefile (mas rapido)
bash build_linux.sh --onedir
```

### Modelos no se descargan
```bash
# Verificar conexion a internet
curl -I https://huggingface.co

# Descargar manualmente
python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-tiny', local_dir='models_ct2/tiny')"
```

---

## 11. CI/CD en Linux

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

## 12. Comandos rapidos de referencia

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

## 13. Notas para el asistente AI (Buffy/Codebuff)

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
