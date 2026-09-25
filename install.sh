#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  install.sh — INSTALADOR DE UN CLIC para AudioClass en Linux
#
#  Doble clic (o bash install.sh) y listo: Python, dependencias, IA y la app.
#  Funciona en Ubuntu/Debian, Fedora/RHEL, Arch Linux, openSUSE.
#
#  Uso:
#    bash install.sh              # Instalación completa
#    bash install.sh --uninstall  # Desinstalar AudioClass
#    bash install.sh --help       # Mostrar ayuda
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Configuración ────────────────────────────────────────────────────────────
APP_NAME="AudioClass"
APP_VERSION="9.1.0"
INSTALL_DIR="$HOME/.local/share/audioclass"
VENV_DIR="$INSTALL_DIR/audioclass_env"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons"
RECORDINGS_DIR="$HOME/AudioClass_Recordings"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ── Funciones auxiliares ─────────────────────────────────────────────────────
log()     { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BOLD}${BLUE}══════ $* ══════${NC}"; }

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO_ID="${ID,,}"  # minúsculas
    elif command -v lsb_release &>/dev/null; then
        DISTRO_ID=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
    else
        DISTRO_ID="unknown"
    fi
}

install_system_deps() {
    step "Instalando dependencias del sistema"

    case "$DISTRO_ID" in
        ubuntu|debian|linuxmint|pop)
            log "Detectado: $DISTRO_ID (Debian/Ubuntu)"
            sudo apt-get update -qq
            sudo apt-get install -y -qq \
                python3 python3-venv python3-pip \
                python3-tk \
                xvfb \
                libportaudio2 \
                libsndfile1 \
                libgl1-mesa-glx \
                libglib2.0-0 \
                pulseaudio \
                libpulse0
            ;;
        fedora|rhel|centos|rocky|alma)
            log "Detectado: $DISTRO_ID (Fedora/RHEL)"
            sudo dnf install -y \
                python3 python3-pip python3-tkinter \
                xorg-x11-server-Xvfb \
                portaudio-devel \
                libsndfile \
                mesa-libGL \
                glib2 \
                pulseaudio-libs
            ;;
        arch|manjaro|endeavouros)
            log "Detectado: $DISTRO_ID (Arch)"
            sudo pacman -S --needed --noconfirm \
                python python-pip tk \
                xorg-server-xvfb \
                portaudio \
                libsndfile \
                mesa \
                glib2 \
                libpulse
            ;;
        opensuse*|suse)
            log "Detectado: openSUSE/SUSE"
            sudo zypper install -y \
                python3 python3-pip python3-tk \
                xorg-x11-server-Xvfb \
                portaudio-devel \
                libsndfile \
                Mesa-libGL \
                glib2 \
                libpulse0
            ;;
        *)
            warn "Distribución no reconocida: $DISTRO_ID"
            warn "Intentando instalar dependencias con el gestor de paquetes..."
            # Intentar detectar el gestor de paquetes
            if command -v apt-get &>/dev/null; then
                sudo apt-get update -qq
                sudo apt-get install -y python3 python3-venv python3-pip python3-tk xvfb libportaudio2 libsndfile1
            elif command -v dnf &>/dev/null; then
                sudo dnf install -y python3 python3-pip python3-tkinter portaudio-devel libsndfile
            elif command -v pacman &>/dev/null; then
                sudo pacman -S --needed --noconfirm python python-pip tk portaudio libsndfile
            else
                error "No se pudo detectar el gestor de paquetes"
                error "Instala manualmente: python3, python3-tk, portaudio, libsndfile"
                exit 1
            fi
            ;;
    esac
    log "Dependencias del sistema instaladas"
}

find_python() {
    step "Buscando Python"

    # Buscar python3 en el PATH
    if command -v python3 &>/dev/null; then
        PY="$(command -v python3)"
        PY_VERSION="$($PY --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')"

        # Verificar que sea Python 3.9+
        PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
            log "Python encontrado: $PY ($PY_VERSION)"
            return 0
        else
            warn "Python encontrado pero es muy viejo ($PY_VERSION, necesita 3.9+)"
        fi
    fi

    # Python no encontrado o muy viejo
    error "No se encontró Python 3.9+ en tu sistema"
    echo ""
    echo "  Instálalo con tu gestor de paquetes:"
    echo ""
    case "$DISTRO_ID" in
        ubuntu|debian|linuxmint|pop)
            echo "    sudo apt install python3 python3-venv python3-tk"
            ;;
        fedora|rhel|centos|rocky|alma)
            echo "    sudo dnf install python3 python3-tkinter"
            ;;
        arch|manjaro|endeavouros)
            echo "    sudo pacman -S python tk"
            ;;
        *)
            echo "    sudo apt install python3 python3-venv python3-tk"
            echo "    # o"
            echo "    sudo dnf install python3 python3-tkinter"
            echo "    # o"
            echo "    sudo pacman -S python tk"
            ;;
    esac
    echo ""
    echo "  Después de instalarlo, vuelve a ejecutar: bash install.sh"
    exit 1
}

create_venv() {
    step "Creando entorno virtual"

    if [ -d "$VENV_DIR" ]; then
        log "Ya existe un entorno virtual en $VENV_DIR"
        log "Reutilizando..."
    else
        "$PY" -m venv "$VENV_DIR"
        log "Entorno virtual creado en $VENV_DIR"
    fi

    VENV_PY="$VENV_DIR/bin/python"
    "$VENV_PY" -m pip install --upgrade pip --quiet
}

install_python_deps() {
    step "Instalando librerías de Python"

    # PyTorch CPU primero (ligero, sin GPU)
    echo -e "  ${BLUE}Paso 1/2: PyTorch CPU (ligero)...${NC}"
    "$VENV_PY" -m pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet 2>/dev/null || \
        warn "No se pudo instalar PyTorch CPU, se usará el estándar"

    # Resto de dependencias
    echo -e "  ${BLUE}Paso 2/2: Whisper, Gemini, interfaz...${NC}"
    "$VENV_PY" -m pip install -r requirements_v91.txt --quiet

    log "Librerías instaladas"
}

download_models() {
    step "Descargando modelos de voz"

    echo -e "  ${BLUE}Descargando modelo Whisper tiny (primera vez)...${NC}"
    "$VENV_PY" -c "import whisper; whisper.load_model('tiny')" 2>/dev/null || \
        warn "No se pudo descargar el modelo. La app lo descargará al transcribir."

    log "Modelos listos"
}

test_gemini() {
    step "Probando conexión con Gemini (opcional)"

    if [ -f test_gemini_v91.py ]; then
        "$VENV_PY" test_gemini_v91.py || true
    else
        warn "test_gemini_v91.py no encontrado, saltando prueba"
    fi

    echo ""
    echo "  Si no tienes API Key, puedes configurarla después:"
    echo "    Configuración → pegar tu clave → Probar Conexión"
}

create_desktop_entry() {
    step "Creando acceso directo en el escritorio"

    # Directorio de la app (donde está este script)
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Crear script de inicio
    mkdir -p "$BIN_DIR"
    cat > "$BIN_DIR/audioclass" << LAUNCHER
#!/usr/bin/env bash
cd "$APP_DIR"
"$VENV_DIR/bin/python" audioclass_v91.py "\$@"
LAUNCHER
    chmod +x "$BIN_DIR/audioclass"
    log "Script de inicio: $BIN_DIR/audioclass"

    # Crear .desktop file
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/audioclass.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=AudioClass
GenericName=Grabador de Clases
Comment=Graba, transcribe y exporta clases universitarias con IA
Exec=$BIN_DIR/audioclass
Icon=audioclass
Terminal=false
Categories=Education;Audio;Utility;
MimeType=audio/wav;audio/x-wav;
StartupWMClass=AudioClass
Keywords=grabar;transcribir;clase;universidad;whisper;gemini;
DESKTOP
    chmod +x "$DESKTOP_DIR/audioclass.desktop"
    log "Acceso directo: $DESKTOP_DIR/audioclass.desktop"

    # Crear icono (placeholder si no existe uno real)
    mkdir -p "$ICON_DIR/hicolor/256x256/apps"
    if [ -f "$APP_DIR/assets/audioclass_icon.png" ]; then
        cp "$APP_DIR/assets/audioclass_icon.png" "$ICON_DIR/hicolor/256x256/apps/audioclass.png"
    else
        # Crear icono placeholder con Python
        "$VENV_PY" -c "
from PIL import Image, ImageDraw
img = Image.new('RGB', (256, 256), '#0F172A')
d = ImageDraw.Draw(img)
d.rectangle([20, 20, 236, 236], fill='#1E293B', outline='#60A5FA', width=4)
d.text((80, 90), 'AC', fill='#60A5FA')
img.save('$ICON_DIR/hicolor/256x256/apps/audioclass.png')
" 2>/dev/null || warn "No se pudo crear el icono (falta Pillow)"
    fi
    log "Icono instalado"

    # Actualizar base de datos de iconos
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$ICON_DIR/hicolor" 2>/dev/null || true
    fi

    # Actualizar base de datos de desktop files
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
}

create_launcher_script() {
    step "Creando script de inicio rápido"

    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Script en la carpeta de la app
    cat > "$APP_DIR/Iniciar AudioClass.sh" << LAUNCHER
#!/usr/bin/env bash
cd "$APP_DIR"
"$VENV_DIR/bin/python" audioclass_v91.py
LAUNCHER
    chmod +x "$APP_DIR/Iniciar AudioClass.sh"
    log "Script de inicio: Iniciar AudioClass.sh"
}

show_summary() {
    APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║  ¡TODO LISTO!                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Para abrir AudioClass:                                              ║${NC}"
    echo -e "${BOLD}${GREEN}║    • Icono \"AudioClass\" en tu escritorio o menú de aplicaciones    ║${NC}"
    echo -e "${BOLD}${GREEN}║    • Terminal: audioclass                                            ║${NC}"
    echo -e "${BOLD}${GREEN}║    • Script: Iniciar AudioClass.sh                                   ║${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Tus grabaciones se guardan en:                                     ║${NC}"
    echo -e "${BOLD}${GREEN}║    $RECORDINGS_DIR${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Guía completa: GUIA_DE_USO.md                                     ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

uninstall() {
    step "Desinstalando AudioClass"

    echo "Esto eliminará:"
    echo "  • $INSTALL_DIR"
    echo "  • $BIN_DIR/audioclass"
    echo "  • $DESKTOP_DIR/audioclass.desktop"
    echo "  • $ICON_DIR/hicolor/256x256/apps/audioclass.png"
    echo ""
    echo -n "¿Continuar? (s/N): "
    read -r CONFIRM
    if [[ ! "$CONFIRM" =~ ^[sS]$ ]]; then
        echo "Cancelado."
        exit 0
    fi

    rm -rf "$INSTALL_DIR"
    rm -f "$BIN_DIR/audioclass"
    rm -f "$DESKTOP_DIR/audioclass.desktop"
    rm -f "$ICON_DIR/hicolor/256x256/apps/audioclass.png"

    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache -f -t "$ICON_DIR/hicolor" 2>/dev/null || true
    fi
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi

    log "AudioClass desinstalado"
    echo ""
    echo "  Tus grabaciones en $RECORDINGS_DIR NO se eliminaron."
    echo "  Para eliminarlas: rm -rf $RECORDINGS_DIR"
}

show_help() {
    echo "AudioClass v$APP_VERSION — Instalador para Linux"
    echo ""
    echo "Uso:"
    echo "  bash install.sh              Instalación completa"
    echo "  bash install.sh --uninstall  Desinstalar AudioClass"
    echo "  bash install.sh --help       Mostrar esta ayuda"
    echo ""
    echo "Requisitos:"
    echo "  • Linux (Ubuntu, Fedora, Arch, openSUSE o similar)"
    echo "  • Python 3.9+"
    echo "  • Conexión a internet (para instalar dependencias)"
    echo "  • ~2 GB de espacio libre"
    echo ""
    echo "La instalación tarda 10-20 minutos la primera vez."
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    # Parsear argumentos
    for arg in "$@"; do
        case "$arg" in
            --uninstall) uninstall; exit 0 ;;
            --help|-h) show_help; exit 0 ;;
        esac
    done

    echo ""
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║                                                                      ║${NC}"
    echo -e "${BOLD}${BLUE}║         AUDIOCLASS v$APP_VERSION — INSTALADOR AUTOMÁTICO             ║${NC}"
    echo -e "${BOLD}${BLUE}║        Doble clic y listo: Python, dependencias, IA y la app         ║${NC}"
    echo -e "${BOLD}${BLUE}║                                                                      ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Este programa hará todo por ti, paso a paso:"
    echo ""
    echo "  [1/6]  Detectar distribución Linux e instalar dependencias del sistema"
    echo "  [2/6]  Buscar Python 3.9+"
    echo "  [3/6]  Crear un espacio aislado para AudioClass"
    echo "  [4/6]  Instalar todas las librerías necesarias"
    echo "  [5/6]  Descargar el modelo de voz (Whisper)"
    echo "  [6/6]  Crear acceso directo y abrir la app"
    echo ""
    echo "Necesitas internet y unos 2 GB de espacio libre."
    echo "La primera vez puede tardar 10-20 minutos."
    echo ""
    read -p "Pulsa Enter para continuar..."

    # Detectar distribución
    detect_distro

    # Paso 1: Dependencias del sistema
    install_system_deps

    # Paso 2: Python
    find_python

    # Paso 3: Entorno virtual
    create_venv

    # Paso 4: Dependencias Python
    install_python_deps

    # Paso 5: Modelos
    download_models

    # Paso 6: Gemini (opcional)
    test_gemini || true

    # Paso 7: Accesos directos
    create_desktop_entry
    create_launcher_script

    # Resumen
    show_summary

    # Abrir la app
    echo "Abriendo AudioClass..."
    "$BIN_DIR/audioclass" &

    echo ""
    echo "La app ya debería estar abierta."
    echo "Si ves un error, revisa la guía de solución de problemas en GUIA_DE_USO.md"
    echo ""
}

main "$@"
