#!/usr/bin/env bash
# build_macos_app.sh — Genera un .app bundle de AudioClass para macOS
# Uso: bash build_macos_app.sh
#
# Genera: dist/AudioClass.app (doble clic en Finder = abre la app)
#
# Requisitos:
#   brew install python@3.12 portaudio
#   pip install -r requirements_v91.txt pyinstaller
#
set -euo pipefail

echo "=== AudioClass v9.1 — Build macOS .app bundle ==="

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

# Build onedir primero (necesario para .app)
echo "[1/4] Build onedir con PyInstaller..."
$PY -m PyInstaller --noconfirm AudioClass_v91.spec

if [ ! -d "dist/AudioClass" ]; then
    echo "ERROR: dist/AudioClass no existe"
    exit 1
fi

# Crear estructura .app
echo "[2/4] Creando estructura AudioClass.app..."
APP="dist/AudioClass.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"

# Copiar ejecutable
cp dist/AudioClass/AudioClass "$APP/Contents/MacOS/AudioClass"
chmod +x "$APP/Contents/MacOS/AudioClass"

# Copiar dependencias (librerías, modelos, etc.)
cp -r dist/AudioClass/* "$APP/Contents/MacOS/"

# Copiar icono si existe
if [ -f "assets/audioclass_icon.icns" ]; then
    cp assets/audioclass_icon.icns "$APP/Contents/Resources/audioclass.icns"
elif [ -f "assets/audioclass_icon.png" ]; then
    # Convertir PNG a ICNS usando sips (macOS nativo)
    TMPICON=$(mktemp -d)/icon_512.png
    sips -z 512 512 assets/audioclass_icon.png --out "$TMPICON" 2>/dev/null || cp assets/audioclass_icon.png "$TMPICON"
    # Crear .iconset mínimo
    ICONSET="$APP/Contents/Resources/audioclass.iconset"
    mkdir -p "$ICONSET"
    cp "$TMPICON" "$ICONSET/icon_512x512.png"
    iconutil --convert icns "$ICONSET" --output "$APP/Contents/Resources/audioclass.icns" 2>/dev/null || \
        cp "$TMPICON" "$APP/Contents/Resources/audioclass.icns"
    rm -rf "$(dirname "$TMPICON")"
fi

# Crear Info.plist
echo "[3/4] Generando Info.plist..."
cat > "$APP/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>AudioClass</string>
    <key>CFBundleDisplayName</key>
    <string>AudioClass</string>
    <key>CFBundleIdentifier</key>
    <string>com.audioclass.app</string>
    <key>CFBundleVersion</key>
    <string>9.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>9.1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>AudioClass</string>
    <key>CFBundleIconFile</key>
    <string>audioclass</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>NSMicrophoneUsageDescription</key>
    <string>AudioClass necesita acceso al micrófono para grabar clases universitarias.</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.education</string>
</dict>
</plist>
PLIST

# Copiar documentos legales
for doc in LEEME.txt LICENCIA.txt EULA.txt AVISO_DE_PRIVACIDAD.txt TERCEROS_Y_LICENCIAS.md; do
    [ -f "$doc" ] && cp "$doc" "$APP/Contents/MacOS/"
done

echo "[4/4] Verificando .app bundle..."
if [ -f "$APP/Contents/MacOS/AudioClass" ] && [ -f "$APP/Contents/Info.plist" ]; then
    echo "=== macOS .app bundle creado: $APP ==="
    ls -la "$APP"
    echo ""
    echo "Tamaño: $(du -sh "$APP" | cut -f1)"
    echo ""
    echo "Para instalar: arrastra AudioClass.app a /Applications/"
    echo "Para probar: open $APP"
else
    echo "ERROR: .app bundle incompleto"
    exit 1
fi

# Crear .dmg (opcional, si hdiutil está disponible)
if command -v hdiutil &>/dev/null; then
    echo ""
    echo "Creando .dmg para distribución..."
    DMG="AudioClass_v9.1_MACOS.dmg"
    hdiutil create -volname "AudioClass" -srcfolder "$APP" -ov -format UDZO "$DMG" 2>/dev/null
    if [ -f "$DMG" ]; then
        echo "=== DMG creado: $DMG ($(du -sh "$DMG" | cut -f1)) ==="
        echo "Los usuarios solo necesitan: abrir .dmg → arrastrar a Applications"
    else
        echo "WARN: No se pudo crear .dmg (no es crítico)"
    fi
fi

echo ""
echo "=== BUILD macOS APP OK ==="
