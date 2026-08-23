#!/bin/bash
# build_appimage.sh — Construye un AppImage de AudioClass para Linux
# Requisitos: Python 3.12+, pip, appimagetool
# Uso: bash build_appimage.sh
set -e

echo "=== AudioClass v9.1 — Build AppImage ==="

# 1. Build onedir con PyInstaller
echo "[1/5] Build onedir..."
python -m PyInstaller AudioClass_v91_linux.spec --clean --noconfirm 2>&1 | tail -3

if [ ! -d "dist/AudioClass" ]; then
    echo "ERROR: dist/AudioClass no existe"
    exit 1
fi

# 2. Crear estructura AppDir
echo "[2/5] Creando AppDir..."
APPDIR="AudioClass.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copiar ejecutable y dependencias
cp -r dist/AudioClass/* "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/AudioClass"

# 3. Desktop file
echo "[3/5] Creando desktop file..."
cat > "$APPDIR/audioclass.desktop" << 'EOF'
[Desktop Entry]
Type=Application
Name=AudioClass
Comment=Graba, transcribe y exporta clases universitarias con IA
Exec=AudioClass
Icon=audioclass
Categories=Education;Audio;Utility;
Terminal=false
StartupWMClass=AudioClass
EOF

cp "$APPDIR/audioclass.desktop" "$APPDIR/usr/share/applications/audioclass.desktop"

# 4. Icon (placeholder — usar assets/ si existe)
echo "[4/5] Configurando icono..."
if [ -f "assets/audioclass_icon.png" ]; then
    cp assets/audioclass_icon.png "$APPDIR/usr/share/icons/hicolor/256x256/apps/audioclass.png"
    cp assets/audioclass_icon.png "$APPDIR/audioclass.png"
else
    # Crear icono placeholder minimo
    python -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (256, 256), '#0F172A')
d = ImageDraw.Draw(img)
d.rectangle([40, 40, 216, 216], fill='#1E293B', outline='#60A5FA', width=4)
d.text((80, 100), 'AC', fill='#60A5FA')
img.save('$APPDIR/usr/share/icons/hicolor/256x256/apps/audioclass.png')
img.save('$APPDIR/audioclass.png')
" 2>/dev/null || echo "WARN: No PIL, usando icono generico"
fi

# 5. Empaquetar AppImage con update info
echo "[5/5] Empaquetando AppImage..."

# URL de update info para AppImageUpdate (zsync differential updates)
UPDATE_INFO="gh-releases-zsync|Nagamot-Byt|AudioClass|latest|AudioClass_*x86_64.AppImage.zsync"

# Buscar appimagetool
APPIMAGETOOL=""
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
elif [ -f /tmp/appimagetool ]; then
    APPIMAGETOOL="/tmp/appimagetool"
else
    echo "appimagetool no encontrado. Descargando..."
    curl -sL https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -o /tmp/appimagetool
    chmod +x /tmp/appimagetool
    APPIMAGETOOL="/tmp/appimagetool"
fi

if [ -z "$APPIMAGETOOL" ] || [ ! -x "$APPIMAGETOOL" ]; then
    echo "ERROR: No se puede crear AppImage (falta appimagetool)"
    echo "Instala: sudo apt install appimagetool"
    exit 1
fi

# Crear AppImage CON update info (genera .zsync automáticamente)
echo "  Update info: $UPDATE_INFO"
ARCH=x86_64 "$APPIMAGETOOL" -u "$UPDATE_INFO" "$APPDIR" "AudioClass_v9.1_Linux.AppImage" 2>&1 | tail -5

# Verificar que se generó el .zsync
if [ -f "AudioClass_v9.1_Linux.AppImage.zsync" ]; then
    echo "  .zsync generado: $(ls -lh AudioClass_v9.1_Linux.AppImage.zsync | awk '{print $5}')"
else
    echo "  WARN: .zsync no se generó (AppImageUpdate no funcionará)"
fi

echo "=== AppImage creada: AudioClass_v9.1_Linux.AppImage ==="
ls -lh AudioClass_v9.1_Linux.AppImage AudioClass_v9.1_Linux.AppImage.zsync 2>/dev/null

echo "=== LISTO ==="
