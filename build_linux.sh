#!/usr/bin/env bash
# build_linux.sh — Compila AudioClass para Linux con PyInstaller
# Uso: bash build_linux.sh [--onedir | --onefile]
#
# Requisitos (Ubuntu/Debian):
#   sudo apt install python3-pip python3-venv xvfb libportaudio2 libsndfile1 \
#     libgl1-mesa-glx libglib2.0-0
#   pip install -r requirements_v91.txt pyinstaller
#
set -euo pipefail

MODE="${1:---onefile}"
echo "=== AudioClass build Linux ($MODE) ==="

PY="$(command -v python3 || command -v python)"
echo "Python: $PY ($($PY --version 2>&1))"

# Dependencias del sistema
if command -v apt-get &>/dev/null; then
    echo "Instalando dependencias del sistema..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq xvfb libportaudio2 libsndfile1 \
        libgl1-mesa-glx libglib2.0-0
fi

# Dependencias Python
$PY -m pip install --quiet -r requirements_v91.txt pyinstaller

# Modelos
if [ ! -f models/tiny.pt ]; then
    echo "Descargando modelos whisper..."
    $PY -c "
import os, shutil, whisper
for name in ('tiny', 'base'):
    whisper.load_model(name)
os.makedirs('models', exist_ok=True)
shutil.copy(os.path.expanduser('~/.cache/whisper/tiny.pt'), 'models/tiny.pt')
print('WHISPER_PT_READY')
"
fi

if [ ! -f models_ct2/base/model.bin ]; then
    echo "Descargando modelos CT2..."
    $PY -c "
from huggingface_hub import snapshot_download
for name in ('tiny', 'base'):
    snapshot_download(f'Systran/faster-whisper-{name}', local_dir=f'models_ct2/{name}')
print('CT2_READY')
"
fi

# Build
if [ "$MODE" = "--onedir" ]; then
    $PY -m PyInstaller --noconfirm AudioClass_v91.spec
    echo "=== Build onedir completo ==="
    ls -la dist/AudioClass/AudioClass
    # Selftest
    echo "=== Selftest ==="
    xvfb-run -a dist/AudioClass/AudioClass --selftest-transcribe tts_clase.wav /tmp/selftest_out.txt || true
    cat /tmp/selftest_out.txt 2>/dev/null | head -3
else
    $PY -m PyInstaller --noconfirm AudioClass_v91_onefile.spec
    echo "=== Build onefile completo ==="
    ls -la dist_onefile/AudioClass
    # Selftest
    echo "=== Selftest ==="
    xvfb-run -a dist_onefile/AudioClass --selftest-transcribe tts_clase.wav /tmp/selftest_out.txt || true
    cat /tmp/selftest_out.txt 2>/dev/null | head -3
fi

echo "=== BUILD LINUX OK ==="
