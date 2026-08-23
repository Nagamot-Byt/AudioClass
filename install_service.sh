#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  install_service.sh — Instala AudioClass como servicio systemd
#
#  Uso:
#    sudo bash install_service.sh              # Instalar y habilitar
#    sudo bash install_service.sh --uninstall  # Desinstalar servicio
#    sudo bash install_service.sh --status     # Ver estado
#    sudo bash install_service.sh --logs       # Ver logs en vivo
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SERVICE_NAME="audioclass"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_DIR="/opt/audioclass"
VENV_DIR="${INSTALL_DIR}/audioclass_env"
DATA_DIR="/var/lib/audioclass"
CONFIG_DIR="/etc/audioclass"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log()  { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }
step() { echo -e "\n${BOLD}${BLUE}══════ $* ══════${NC}"; }

# ── Verificar root ───────────────────────────────────────────────────────────
check_root() {
    if [ "$EUID" -ne 0 ]; then
        error "Este script requiere permisos de root (sudo)"
        exit 1
    fi
}

# ── Detectar Python ──────────────────────────────────────────────────────────
find_python() {
    if command -v python3 &>/dev/null; then
        PY="$(command -v python3)"
    else
        error "Python3 no encontrado"
        exit 1
    fi
    log "Python: $PY ($($PY --version 2>&1))"
}

# ── Instalar servicio ────────────────────────────────────────────────────────
install_service() {
    step "Instalando servicio ${SERVICE_NAME}"

    # Crear usuario del servicio
    if ! id -u audioclass &>/dev/null; then
        useradd --system --no-create-home --shell /usr/sbin/nologin audioclass
        log "Usuario 'audioclass' creado"
    else
        log "Usuario 'audioclass' ya existe"
    fi

    # Crear directorios
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$DATA_DIR"
    mkdir -p "$CONFIG_DIR"

    # Copiar código fuente
    log "Copiando código fuente..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cp -r "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
    cp -r "$SCRIPT_DIR"/assets "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/models_ct2 "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/models "$INSTALL_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/requirements_v91.txt "$INSTALL_DIR/"

    # Crear entorno virtual
    if [ ! -d "$VENV_DIR" ]; then
        log "Creando entorno virtual..."
        "$PY" -m venv "$VENV_DIR"
    fi

    # Instalar dependencias
    log "Instalando dependencias..."
    "$VENV_DIR/bin/pip" install --upgrade pip --quiet
    "$VENV_DIR/bin/pip" install --quiet fastapi uvicorn python-multipart
    "$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements_v91.txt"

    # Descargar modelo whisper
    log "Verificando modelo Whisper..."
    "$VENV_DIR/bin/python" -c "import whisper; whisper.load_model('tiny')" 2>/dev/null || \
        warn "Modelo no descargado (se descargará al iniciar)"

    # Configurar permisos
    chown -R audioclass:audioclass "$INSTALL_DIR"
    chown -R audioclass:audioclass "$DATA_DIR"
    chmod 755 "$INSTALL_DIR"

    # Copiar servicio
    log "Instalando servicio systemd..."
    cp "$SCRIPT_DIR/audioclass.service" "$SERVICE_FILE"
    systemctl daemon-reload

    # Habilitar e iniciar
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"

    log "Servicio instalado y iniciado"

    # Verificar estado
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "Servicio ${SERVICE_NAME} está CORRIENDO"
    else
        warn "El servicio no está corriendo. Verifica con: journalctl -u ${SERVICE_NAME}"
    fi
}

# ── Desinstalar servicio ─────────────────────────────────────────────────────
uninstall_service() {
    step "Desinstalando servicio ${SERVICE_NAME}"

    echo "Esto eliminará:"
    echo "  • Servicio systemd: $SERVICE_FILE"
    echo "  • Directorio de instalación: $INSTALL_DIR"
    echo "  • Directorio de datos: $DATA_DIR"
    echo "  • Usuario: audioclass"
    echo ""
    echo -n "¿Continuar? (s/N): "
    read -r CONFIRM
    if [[ ! "$CONFIRM" =~ ^[sS]$ ]]; then
        echo "Cancelado."
        exit 0
    fi

    # Detener y deshabilitar
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true

    # Eliminar servicio
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload

    # Eliminar archivos
    rm -rf "$INSTALL_DIR"
    rm -rf "$DATA_DIR"
    rm -rf "$CONFIG_DIR"

    # Eliminar usuario
    userdel audioclass 2>/dev/null || true

    log "Servicio desinstalado"
}

# ── Ver estado ───────────────────────────────────────────────────────────────
show_status() {
    step "Estado del servicio ${SERVICE_NAME}"
    systemctl status "$SERVICE_NAME" --no-pager || true
    echo ""
    echo "Puerto: $(grep AUDIOCLASS_PORT /etc/systemd/system/${SERVICE_NAME}.service 2>/dev/null | cut -d= -f2 || echo '8000')"
    echo "Logs: journalctl -u ${SERVICE_NAME} -f"
}

# ── Ver logs ─────────────────────────────────────────────────────────────────
show_logs() {
    journalctl -u "$SERVICE_NAME" -f --no-pager
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    for arg in "$@"; do
        case "$arg" in
            --uninstall) uninstall_service; exit 0 ;;
            --status) show_status; exit 0 ;;
            --logs) show_logs; exit 0 ;;
            --help|-h)
                echo "Uso: sudo bash install_service.sh [opciones]"
                echo ""
                echo "Opciones:"
                echo "  (ninguna)     Instalar y habilitar el servicio"
                echo "  --uninstall   Desinstalar el servicio"
                echo "  --status      Ver estado del servicio"
                echo "  --logs        Ver logs en vivo"
                echo "  --help        Mostrar esta ayuda"
                exit 0
                ;;
        esac
    done

    echo ""
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║  AudioClass — Instalación como servicio systemd                    ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_root
    find_python
    install_service

    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║  ¡Servicio instalado!                                               ║${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Endpoints:                                                          ║${NC}"
    echo -e "${BOLD}${GREEN}║    POST http://localhost:8000/transcribe    (audio → texto)         ║${NC}"
    echo -e "${BOLD}${GREEN}║    POST http://localhost:8000/transcribe/advanced (audio → análisis)║${NC}"
    echo -e "${BOLD}${GREEN}║    GET  http://localhost:8000/status         (estado del servidor)   ║${NC}"
    echo -e "${BOLD}${GREEN}║    GET  http://localhost:8000/docs           (documentación Swagger)║${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Comandos:                                                           ║${NC}"
    echo -e "${BOLD}${GREEN}║    systemctl status audioclass                                     ║${NC}"
    echo -e "${BOLD}${GREEN}║    journalctl -u audioclass -f                                     ║${NC}"
    echo -e "${BOLD}${GREEN}║    curl -X POST http://localhost:8000/transcribe -F file=@audio.wav║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

main "$@"
