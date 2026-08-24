#!/usr/bin/env bash
# ============================================================
#  launch_linux.sh — Lanzador un clic de AudioClass para Linux
# ============================================================
#  Verifica dependencias del sistema y Python, instala lo que
#  falte (con confirmacion), y arranca la app.
#
#  Uso:
#    chmod +x launch_linux.sh
#    ./launch_linux.sh
#
#  Prioridad de arranque:
#    1. Binario compilado (dist/AudioClass/AudioClass)
#    2. AppImage (AudioClass_v9.1_Linux.AppImage)
#    3. Source (python3 audioclass_v91.py)
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colores (sin ANSI si no hay terminal)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

ok()   { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }
info() { echo -e "  ${BLUE}ℹ️${NC}  $1"; }

ERRORS=0

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       AudioClass v9.1 — Lanzador Linux           ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================
#  1. Verificar SO
# ============================================================
echo -e "${BOLD}[1/6] Verificando sistema operativo...${NC}"
OS="$(uname -s)"
ARCH="$(uname -m)"
if [ "$OS" != "Linux" ]; then
    fail "Este script es solo para Linux (detectado: $OS)"
    fail "En macOS usa: ./build_macos_app.sh run"
    fail "En Windows usa: quick_start.bat"
    exit 1
fi
ok "Linux $ARCH"

# ============================================================
#  2. Detectar Python
# ============================================================
echo ""
echo -e "${BOLD}[2/6] Verificando Python...${NC}"
PYTHON=""
PYTHON_VER=""

for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        ver="$($candidate --version 2>&1 | grep -oP '\d+\.\d+')"
        major="${ver%%.*}"
        minor="${ver##*.}"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            PYTHON_VER="$ver"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    fail "Python >= 3.10 no encontrado"
    echo ""
    echo "  Instalalo con:"
    echo "    Ubuntu/Debian: sudo apt install python3.12 python3.12-venv python3-pip"
    echo "    Fedora:        sudo dnf install python3.12"
    echo "    Arch:          sudo pacman -S python"
    exit 1
fi
ok "Python $PYTHON_VER ($PYTHON)"

# ============================================================
#  3. Verificar dependencias del sistema (PortAudio, etc.)
# ============================================================
echo ""
echo -e "${BOLD}[3/6] Verificando dependencias del sistema...${NC}"

check_sys_pkg() {
    local pkg="$1"
    local desc="$2"
    if dpkg -s "$pkg" &>/dev/null 2>&1; then
        ok "$desc instalado"
        return 0
    elif rpm -q "$pkg" &>/dev/null 2>&1; then
        ok "$desc instalado"
        return 0
    elif pacman -Qi "$pkg" &>/dev/null 2>&1; then
        ok "$desc instalado"
        return 0
    else
        fail "$desc NO encontrado"
        return 1
    fi
}

SYS_MISSING=0

# PortAudio (necesario para grabar audio)
if python3 -c "import sounddevice" 2>/dev/null; then
    ok "sounddevice (PortAudio) disponible"
else
    # Verificar si la libreria del sistema esta
    if ldconfig -p 2>/dev/null | grep -q libportaudio; then
        ok "libportaudio.so encontrado"
    elif [ -f /usr/lib/x86_64-linux-gnu/libportaudio.so.2 ] || \
         [ -f /usr/lib64/libportaudio.so.2 ] || \
         [ -f /usr/lib/libportaudio.so.2 ]; then
        ok "libportaudio.so encontrado"
    else
        fail "PortAudio no encontrado — necesario para grabar audio"
        SYS_MISSING=1
        info "Instala con: sudo apt install libportaudio2 (Ubuntu/Debian)"
        info "             sudo dnf install portaudio (Fedora)"
        info "             sudo pacman -S portaudio (Arch)"
    fi
fi

# Audio subsystem (PulseAudio/PipeWire/ALSA)
if command -v pactl &>/dev/null; then
    ok "PulseAudio/PipeWire disponible"
elif [ -d /proc/asound ]; then
    ok "ALSA disponible"
else
    warn "No se detecto subsistema de audio (PulseAudio/PipeWire/ALSA)"
    info "La grabacion puede no funcionar sin un servidor de audio"
fi

# Display server (para la GUI)
if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        ok "Wayland display detectado"
    else
        ok "X11 display detectado"
    fi
else
    fail "No se detecto servidor grafico (DISPLAY vacio)"
    info "Ejecuta desde un entorno de escritorio o usa:"
    info "  export DISPLAY=:0"
    SYS_MISSING=1
fi

# tkinter
if $PYTHON -c "import tkinter" 2>/dev/null; then
    ok "tkinter disponible"
else
    fail "tkinter no encontrado"
    info "Instala con: sudo apt install python3-tk (Ubuntu/Debian)"
    SYS_MISSING=1
fi

if [ "$SYS_MISSING" -gt 0 ]; then
    echo ""
    warn "Faltan dependencias del sistema. Intenta instalarlas y vuelve a ejecutar."
fi

# ============================================================
#  4. Verificar/crear entorno virtual e instalar deps Python
# ============================================================
echo ""
echo -e "${BOLD}[4/6] Verificando dependencias Python...${NC}"

VENV_DIR="$SCRIPT_DIR/venv"
REQ_FILE="$SCRIPT_DIR/requirements_v91.txt"

# Detectar si sounddevice funciona (dependencia critica)
if $PYTHON -c "import sounddevice, numpy, scipy" 2>/dev/null; then
    ok "Dependencias criticas: sounddevice, numpy, scipy"
else
    if [ ! -d "$VENV_DIR" ]; then
        info "Creando entorno virtual..."
        $PYTHON -m venv "$VENV_DIR"
        ok "Entorno virtual creado"
    fi

    source "$VENV_DIR/bin/activate"
    PYTHON="python"

    if [ -f "$REQ_FILE" ]; then
        info "Instalando dependencias desde requirements_v91.txt..."
        info "(Esto puede tardar 2-5 minutos la primera vez)"
        pip install --upgrade pip --quiet 2>/dev/null
        pip install -r "$REQ_FILE" --quiet 2>&1 | tail -3
        ok "Dependencias Python instaladas"
    else
        warn "requirements_v91.txt no encontrado, instalando deps basicas..."
        pip install --upgrade pip --quiet 2>/dev/null
        pip install customtkinter numpy scipy sounddevice noisereduce \
                    fpdf2 matplotlib requests --quiet 2>&1 | tail -3
        ok "Dependencias basicas instaladas"
    fi
fi

# Verificar PyAudio/sounddevice funciona
if $PYTHON -c "import sounddevice as sd; sd.query_devices()" 2>/dev/null | grep -q input; then
    DEVS=$($PYTHON -c "import sounddevice as sd; print(len([d for d in sd.query_devices() if d['max_input_channels']>=1]))")
    ok "Microfonos detectados: $DEVS"
else
    warn "No se pudieron enumerar dispositivos de audio"
    info "Puede que PortAudio no este instalado correctamente"
fi

# ============================================================
#  5. Seleccionar modo de arranque
# ============================================================
echo ""
echo -e "${BOLD}[5/6] Buscando AudioClass...${NC}"

BINARY="$SCRIPT_DIR/dist/AudioClass/AudioClass"
APPIMAGE=$(find "$SCRIPT_DIR" -maxdepth 1 -name "*.AppImage" 2>/dev/null | head -1)
SOURCE="$SCRIPT_DIR/audioclass_v91.py"

LAUNCH_MODE=""
LAUNCH_CMD=""

if [ -x "$BINARY" ]; then
    LAUNCH_MODE="binario compilado"
    LAUNCH_CMD="$BINARY"
    ok "Binario encontrado: $BINARY"
    ok "Tamano: $(du -h "$BINARY" | cut -f1)"
elif [ -n "$APPIMAGE" ] && [ -x "$APPIMAGE" ]; then
    LAUNCH_MODE="AppImage"
    LAUNCH_CMD="$APPIMAGE"
    ok "AppImage encontrado: $(basename "$APPIMAGE")"
elif [ -f "$SOURCE" ]; then
    LAUNCH_MODE="source (Python)"
    LAUNCH_CMD="$PYTHON $SOURCE"
    ok "Fuente encontrada: $SOURCE"
else
    fail "No se encontro audioclass_v91.py, AppImage ni binario"
    fail "Asegurate de estar en la carpeta del proyecto"
    exit 1
fi

# ============================================================
#  6. Ejecutar
# ============================================================
echo ""
echo -e "${BOLD}[6/6] Iniciando AudioClass...${NC}"
echo -e "  Modo: ${BLUE}$LAUNCH_MODE${NC}"
echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  AudioClass esta arrancando...                    ║${NC}"
echo -e "${BOLD}║  Cierra esta terminal cuando quieras.             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# Ejecutar y capturar exit code
set +e
$LAUNCH_CMD
EXIT_CODE=$?
set -e

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    ok "AudioClass se cerro correctamente."
elif [ "$EXIT_CODE" -eq 124 ]; then
    ok "AudioClass termino (timeout de terminal)."
elif [ "$EXIT_CODE" -eq 130 ]; then
    info "AudioClass interrumpido (Ctrl+C)."
else
    warn "AudioClass termino con codigo de salida: $EXIT_CODE"
    echo ""
    echo "  Si hay errores, verifica:"
    echo "    1. Que el servidor de audio (PulseAudio/PipeWire) este corriendo"
    echo "    2. Que el microfono no este en uso por otra app"
    echo "    3. Que tengas permisos de acceso al audio:"
    echo "       groups | grep -E 'audio|pulse'"

    # Sugerir diagnosticos
    if command -v pactl &>/dev/null; then
        echo ""
        info "Diagnostico PulseAudio:"
        pactl info 2>/dev/null | grep -E "Server|Sink|Source" | head -5
    fi
fi

echo ""
echo "Logs: ~/AudioClass_Recordings/logs/audioclass.log"
echo ""
