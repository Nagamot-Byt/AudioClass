#!/usr/bin/env bash
# build_mac.sh — Compila AudioClass para macOS con PyInstaller
# Uso: bash build_mac.sh [--onedir | --onefile]
#
# Requisitos:
#   brew install python@3.12 portaudio
#   pip install -r requirements_v91.txt pyinstaller
#   pip install faster-whisper  (opcional, para backend rapido)
#
set -euo pipefail

MODE="${1:---onefile}"
echo "=== AudioClass build macOS ($MODE) ==="

# Python
PY="$(command -v python3 || command -v python)"
echo "Python: $PY ($($PY --version 2>&1))"

# Dependencias
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
else
    $PY -m PyInstaller --noconfirm AudioClass_v91_onefile.spec
    echo "=== Build onefile completo ==="
    ls -la dist_onefile/AudioClass
fi

echo "=== BUILD macOS OK ==="
