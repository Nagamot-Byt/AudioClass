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

# Build onedir (necesario para .app bundle)
echo "[3/4] Build onedir..."
$PY -m PyInstaller --noconfirm AudioClass_v91.spec

echo "[4/4] Creando .app bundle..."
APP="dist/AudioClass.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# Copiar ejecutable y dependencias
cp dist/AudioClass/AudioClass "$APP/Contents/MacOS/AudioClass"
chmod +x "$APP/Contents/MacOS/AudioClass"
cp -r dist/AudioClass/* "$APP/Contents/MacOS/"

# Info.plist
cat > "$APP/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key><string>AudioClass</string>
    <key>CFBundleDisplayName</key><string>AudioClass</string>
    <key>CFBundleIdentifier</key><string>com.audioclass.app</string>
    <key>CFBundleVersion</key><string>9.1.0</string>
    <key>CFBundleShortVersionString</key><string>9.1.0</string>
    <key>CFBundlePackageType</key><string>APPL</string>
    <key>CFBundleExecutable</key><string>AudioClass</string>
    <key>NSHighResolutionCapable</key><true/>
    <key>NSMicrophoneUsageDescription</key><string>AudioClass necesita acceso al micrófono para grabar clases.</string>
    <key>LSMinimumSystemVersion</key><string>10.15</string>
    <key>LSApplicationCategoryType</key><string>public.app-category.education</string>
</dict>
</plist>
PLIST

# Docs legales
for doc in LEEME.txt LICENCIA.txt EULA.txt AVISO_DE_PRIVACIDAD.txt TERCEROS_Y_LICENCIAS.md; do
    [ -f "$doc" ] && cp "$doc" "$APP/Contents/MacOS/"
done

echo "=== .app bundle creado: $APP ==="
ls -la "$APP/Contents/MacOS/"

# DMG
if command -v hdiutil &>/dev/null; then
    echo "Creando .dmg..."
    hdiutil create -volname "AudioClass" -srcfolder "$APP" -ov -format UDZO AudioClass_v9.1_MACOS.dmg 2>/dev/null || true
    [ -f AudioClass_v9.1_MACOS.dmg ] && echo "=== DMG: AudioClass_v9.1_MACOS.dmg ==="
fi

echo "=== BUILD macOS OK ==="
