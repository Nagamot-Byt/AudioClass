#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  deploy.sh — Despliega AudioClass en Kubernetes
#
#  Uso:
#    bash k8s/deploy.sh                    # Despliegue completo
#    bash k8s/deploy.sh --dry-run          # Solo simular
#    bash k8s/deploy.sh --delete           # Eliminar despliegue
#    bash k8s/deploy.sh --status           # Ver estado
#    bash k8s/deploy.sh --logs             # Ver logs
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="audioclass"
DRY_RUN=false
DELETE=false
STATUS=false
LOGS=false

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

# Parsear argumentos
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        --delete) DELETE=true ;;
        --status) STATUS=true ;;
        --logs) LOGS=true ;;
        --help|-h)
            echo "Uso: bash k8s/deploy.sh [opciones]"
            echo ""
            echo "Opciones:"
            echo "  (ninguna)    Despliegue completo"
            echo "  --dry-run    Solo simular despliegue"
            echo "  --delete     Eliminar despliegue"
            echo "  --status     Ver estado actual"
            echo "  --logs       Ver logs en vivo"
            exit 0
            ;;
    esac
done

# Verificar kubectl
if ! command -v kubectl &>/dev/null; then
    error "kubectl no encontrado"
    echo "  Instala: https://kubernetes.io/docs/tasks/tools/"
    exit 1
fi

# Verificar conexión al cluster
if ! kubectl cluster-info &>/dev/null; then
    error "No se pudo conectar al cluster de Kubernetes"
    exit 1
fi
log "Conectado al cluster"

# ── Modo status ──────────────────────────────────────────────────────────────
if [ "$STATUS" = true ]; then
    step "Estado del despliegue"
    kubectl get pods,services,ingress,hpa -n "$NAMESPACE" 2>/dev/null || \
        warn "No hay recursos desplegados en namespace $NAMESPACE"
    exit 0
fi

# ── Modo logs ────────────────────────────────────────────────────────────────
if [ "$LOGS" = true ]; then
    step "Logs de AudioClass"
    kubectl logs -f -l app.kubernetes.io/name=audioclass -n "$NAMESPACE" --tail=100
    exit 0
fi

# ── Modo delete ──────────────────────────────────────────────────────────────
if [ "$DELETE" = true ]; then
    step "Eliminando despliegue"
    echo "Esto eliminará todos los recursos de AudioClass en Kubernetes"
    echo ""
    echo -n "¿Continuar? (s/N): "
    read -r CONFIRM
    if [[ ! "$CONFIRM" =~ ^[sS]$ ]]; then
        echo "Cancelado."
        exit 0
    fi

    kubectl delete -f "$SCRIPT_DIR/" --ignore-not-found -n "$NAMESPACE"
    kubectl delete namespace "$NAMESPACE" --ignore-not-found
    log "Despliegue eliminado"
    exit 0
fi

# ── Modo deploy ──────────────────────────────────────────────────────────────
step "Desplegando AudioClass en Kubernetes"

# Flags para dry-run
DRY_FLAG=""
if [ "$DRY_RUN" = true ]; then
    DRY_FLAG="--dry-run=client -o yaml"
    warn "Modo dry-run: solo simular despliegue"
fi

# 1. Namespace
step "[1/8] Namespace"
kubectl apply -f "$SCRIPT_DIR/namespace.yaml" $DRY_FLAG
log "Namespace configurado"

# 2. ConfigMap
step "[2/8] ConfigMap"
kubectl apply -f "$SCRIPT_DIR/configmap.yaml" $DRY_FLAG
log "ConfigMap configurado"

# 3. Secret
step "[3/8] Secret"
if grep -q '""' "$SCRIPT_DIR/secret.yaml"; then
    warn "Secret contiene valores vacíos"
    warn "Edita k8s/secret.yaml con tus API keys antes de usar"
fi
kubectl apply -f "$SCRIPT_DIR/secret.yaml" $DRY_FLAG
log "Secret configurado"

# 4. PersistentVolumeClaim
step "[4/8] PersistentVolumeClaim"
kubectl apply -f "$SCRIPT_DIR/pvc.yaml" $DRY_FLAG
log "PVC configurado (10Gi)"

# 5. Deployment
step "[5/8] Deployment"
kubectl apply -f "$SCRIPT_DIR/deployment.yaml" $DRY_FLAG
log "Deployment configurado (2 réplicas)"

# 6. Service
step "[6/8] Service"
kubectl apply -f "$SCRIPT_DIR/service.yaml" $DRY_FLAG
log "Service configurado (ClusterIP)"

# 7. Ingress
step "[7/8] Ingress"
kubectl apply -f "$SCRIPT_DIR/ingress.yaml" $DRY_FLAG
log "Ingress configurado"

# 8. HPA + PDB + NetworkPolicy
step "[8/8] HPA + PDB + NetworkPolicy"
kubectl apply -f "$SCRIPT_DIR/hpa.yaml" $DRY_FLAG
kubectl apply -f "$SCRIPT_DIR/pdb.yaml" $DRY_FLAG
kubectl apply -f "$SCRIPT_DIR/networkpolicy.yaml" $DRY_FLAG
log "Auto-scaling y seguridad configurados"

# Esperar a que los pods estén listos
if [ "$DRY_RUN" = false ]; then
    step "Esperando a que los pods estén listos..."
    kubectl wait --for=condition=ready pod \
        -l app.kubernetes.io/name=audioclass \
        -n "$NAMESPACE" \
        --timeout=120s || warn "Timeout esperando pods"
fi

# Resumen
step "Despliegue completado"
echo ""
kubectl get pods,services,ingress,hpa -n "$NAMESPACE" 2>/dev/null || true

echo ""
echo -e "${BOLD}${GREEN}AudioClass desplegado en Kubernetes${NC}"
echo ""
echo "Comandos útiles:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -f -l app.kubernetes.io/name=audioclass -n $NAMESPACE"
echo "  kubectl port-forward svc/audioclass-server 8000:80 -n $NAMESPACE"
echo "  kubectl exec -it \$(kubectl get pod -n $NAMESPACE -l app.kubernetes.io/component=server -o name | head -1) -n $NAMESPACE -- /bin/bash"
