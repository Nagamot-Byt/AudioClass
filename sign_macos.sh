#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  sign_macos.sh — Firma de código para macOS con certificado self-signed
#
#  Crea un certificado autofirmado en el Keychain y firma el .app bundle
#  para que Gatekeeper no bloquee la app completamente.
#
#  NOTA IMPORTANTE:
#  Un certificado self-signed NO desactiva Gatekeeper por completo.
#  El usuario verá: "AudioClass cannot be opened because the developer
#  cannot be verified." pero podrá hacer clic derecho → Abrir para
#  saltarse la advertencia. Con un certificado de Apple Developer ($99/año)
#  o con notarización de Apple, Gatekeeper no mostraría ninguna advertencia.
#
#  Uso:
#    bash sign_macos.sh                     # Firma el .app bundle
#    bash sign_macos.sh --verify             # Solo verificar firma
#    bash sign_macos.sh --clean              # Eliminar certificado del keychain
#    bash sign_macos.sh --deep               # Firma profunda (todos los binarios)
#
#  Requisitos:
#    - macOS 10.15+
#    - Xcode Command Line Tools (xcode-select --install)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Configuración ────────────────────────────────────────────────────────────
CERT_NAME="AudioClass Self-Signed"
CERT_DAYS=3650  # 10 años
KEYCHAIN="audioclass-signing.keychain-db"
KEYCHAIN_PASSWORD="$(openssl rand -hex 16)"
APP_BUNDLE="dist/AudioClass.app"
DEEP_SIGN=false
VERIFY_ONLY=false
CLEAN_ONLY=false

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

# ── Parsear argumentos ───────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --verify)  VERIFY_ONLY=true ;;
        --clean)   CLEAN_ONLY=true ;;
        --deep)    DEEP_SIGN=true ;;
        --help|-h)
            echo "Uso: bash sign_macos.sh [opciones]"
            echo ""
            echo "Opciones:"
            echo "  (ninguna)   Crea certificado y firma el .app bundle"
            echo "  --verify    Solo verificar la firma actual"
            echo "  --clean     Eliminar el certificado del keychain"
            echo "  --deep      Firma profunda (todos los binarios internos)"
            echo "  --help      Mostrar esta ayuda"
            exit 0
            ;;
    esac
done

# ── Verificar requisitos ─────────────────────────────────────────────────────
check_prerequisites() {
    step "Verificando requisitos"

    # macOS
    if [ "$(uname)" != "Darwin" ]; then
        error "Este script solo funciona en macOS"
        exit 1
    fi
    log "Sistema operativo: macOS"

    # Xcode CLI tools
    if ! command -v codesign &>/dev/null; then
        error "codesign no encontrado. Instala Xcode Command Line Tools:"
        echo "  xcode-select --install"
        exit 1
    fi
    log "codesign disponible"

    # Security framework
    if ! command -v security &>/dev/null; then
        error "security no encontrado"
        exit 1
    fi
    log "security framework disponible"

    # .app bundle
    if [ ! -d "$APP_BUNDLE" ]; then
        error "No se encontró el .app bundle: $APP_BUNDLE"
        echo "  Ejecuta primero: bash build_mac.sh"
        exit 1
    fi
    log "App bundle encontrado: $APP_BUNDLE"
}

# ── Crear certificado self-signed ────────────────────────────────────────────
create_certificate() {
    step "Creando certificado self-signed"

    # Verificar si ya existe
    if security find-identity -v -p codesigning 2>/dev/null | grep -q "$CERT_NAME"; then
        log "Certificado ya existe: $CERT_NAME"
        return 0
    fi

    # Crear keychain temporal para la firma
    log "Creando keychain de firma..."
    security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN" 2>/dev/null || true
    security set-keychain-settings -lut 21600 "$KEYCHAIN" 2>/dev/null || true
    security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN" 2>/dev/null || true

    # Agregar keychain al search list
    security list-keychains -d user -s "$KEYCHAIN" login.keychain 2>/dev/null || true

    # Crear certificado autofirmado
    log "Generando certificado autofirmado..."

    # Crear archivo de configuración del certificado
    CERT_CONFIG=$(mktemp /tmp/cert_config_XXXXXX.cnf)
    cat > "$CERT_CONFIG" << CERTCFG
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
x509_extensions = v3_code_signing

[dn]
CN = $CERT_NAME
O = AudioClass OSS
OU = Development

[v3_code_signing]
basicConstraints = CA:FALSE
keyUsage = digitalSignature
extendedKeyUsage = codeSigning
subjectKeyIdentifier = hash
CERTCFG

    # Generar certificado con openssl
    openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout /tmp/audioclass_signing.key \
        -out /tmp/audioclass_signing.crt \
        -days $CERT_DAYS \
        -config "$CERT_CONFIG" 2>/dev/null

    # Convertir a formato .p12 (PKCS12) para importar al keychain
    openssl pkcs12 -export \
        -in /tmp/audioclass_signing.crt \
        -inkey /tmp/audioclass_signing.key \
        -out /tmp/audioclass_signing.p12 \
        -passout pass:"$KEYCHAIN_PASSWORD" 2>/dev/null

    # Importar al keychain
    log "Importando certificado al keychain..."
    security import /tmp/audioclass_signing.p12 \
        -k "$KEYCHAIN" \
        -P "$KEYCHAIN_PASSWORD" \
        -T /usr/bin/codesign \
        -T /usr/bin/security 2>/dev/null

    # Permitir codesign usar el certificado sin interacción
    security set-key-partition-list -S apple-tool:,apple:,codesign: \
        -s -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN" 2>/dev/null || true

    # Limpiar archivos temporales
    rm -f /tmp/audioclass_signing.key /tmp/audioclass_signing.crt \
          /tmp/audioclass_signing.p12 "$CERT_CONFIG"

    log "Certificado creado: $CERT_NAME"
}

# ── Firmar el .app bundle ────────────────────────────────────────────────────
sign_app() {
    step "Firmando el .app bundle"

    # Verificar que el certificado existe
    if ! security find-identity -v -p codesigning 2>/dev/null | grep -q "$CERT_NAME"; then
        error "No se encontró el certificado: $CERT_NAME"
        echo "  Ejecuta sin --verify para crearlo"
        exit 1
    fi

    # Limpiar firmas anteriores
    log "Limpiando firmas anteriores..."
    codesign --remove-signature "$APP_BUNDLE" 2>/dev/null || true

    # Firma
    SIGN_ARGS="--force --sign \"$CERT_NAME\""
    if [ "$DEEP_SIGN" = true ]; then
        SIGN_ARGS="$SIGN_ARGS --deep"
        log "Firma profunda habilitada"
    fi

    # Agregar opciones de runtime
    SIGN_ARGS="$SIGN_ARGS --options runtime --timestamp"

    log "Firmando $APP_BUNDLE..."
    eval codesign $SIGN_ARGS "\"$APP_BUNDLE\""

    log "App bundle firmado"
}

# ── Verificar firma ──────────────────────────────────────────────────────────
verify_signature() {
    step "Verificando firma del .app bundle"

    echo ""
    echo "=== codesign --verify ==="
    if codesign --verify --verbose=2 "$APP_BUNDLE" 2>&1; then
        log "Firma verificada correctamente"
    else
        warn "Verificación falló (normal con certificado self-signed)"
    fi

    echo ""
    echo "=== codesign --display ==="
    codesign --display --verbose=2 "$APP_BUNDLE" 2>&1 || true

    echo ""
    echo "=== spctl --assess ==="
    echo "(Esto fallará con certificado self-signed — es esperado)"
    spctl --assess --type execute --verbose=2 "$APP_BUNDLE" 2>&1 || true

    echo ""
    echo "=== Info de certificados ==="
    security find-identity -v -p codesigning 2>/dev/null | head -5

    echo ""
    echo "=== Verificación de Gatekeeper ==="
    echo "Con certificado self-signed, el usuario verá:"
    echo "  \"AudioClass cannot be opened because the developer"
    echo "   cannot be verified.\""
    echo ""
    echo "Para abrir la app:"
    echo "  1. Clic derecho en AudioClass.app"
    echo "  2. Seleccionar \"Abrir\""
    echo "  3. Clic en \"Abrir\" en el diálogo de confirmación"
    echo ""
    echo "O alternativamente:"
    echo "  xattr -cr /Applications/AudioClass.app"
    echo "  (Esto elimina la atribución de quarantine)"
}

# ── Limpiar certificado ──────────────────────────────────────────────────────
clean_certificate() {
    step "Eliminando certificado del keychain"

    # Buscar y eliminar identidad
    security delete-identity -c "$CERT_NAME" -t "$KEYCHAIN" 2>/dev/null || true
    security delete-identity -c "$CERT_NAME" -t login.keychain 2>/dev/null || true

    # Eliminar keychain temporal
    security delete-keychain "$KEYCHAIN" 2>/dev/null || true

    # Limpiar archivos temporales
    rm -f /tmp/audioclass_signing.*

    log "Certificado eliminado"
}

# ── Main ─────────────────────────────────────────────────────────────────────
main() {
    echo ""
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${BLUE}║  AudioClass — Firma de código para macOS                           ║${NC}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # Verificar requisitos
    check_prerequisites

    # Modo limpiar
    if [ "$CLEAN_ONLY" = true ]; then
        clean_certificate
        exit 0
    fi

    # Crear certificado si no existe
    create_certificate

    # Modo verificar
    if [ "$VERIFY_ONLY" = true ]; then
        verify_signature
        exit 0
    fi

    # Firmar
    sign_app

    # Verificar
    verify_signature

    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║  ¡App firmada!                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Para distribuir:                                                    ║${NC}"
    echo -e "${BOLD}${GREEN}║    zip -r AudioClass_MACOS.zip AudioClass.app                       ║${NC}"
    echo -e "${BOLD}${GREEN}║                                                                      ║${NC}"
    echo -e "${BOLD}${GREEN}║  Nota: Self-signed no desactiva Gatekeeper por completo.            ║${NC}"
    echo -e "${BOLD}${GREEN}║  El usuario deberá hacer clic derecho → Abrir la primera vez.       ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

main
