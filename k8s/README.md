# AudioClass — Despliegue en Kubernetes

Guía completa para desplegar AudioClass Transcription Server en un cluster de Kubernetes.

## Requisitos

- Kubernetes 1.24+
- kubectl configurado
- (Opcional) Helm 3.x
- (Opcional) Cert-Manager para TLS automático

## Despliegue rápido

```bash
# 1. Clonar repositorio
git clone https://github.com/Nagamot-Byt/AudioClass.git
cd AudioClass

# 2. Configurar secrets (editar con tus API keys)
nano k8s/secret.yaml

# 3. Desplegar
bash k8s/deploy.sh
```

## Estructura de archivos

```
k8s/
├── namespace.yaml        # Namespace dedicado
├── configmap.yaml        # Configuración del servidor
├── secret.yaml           # API keys (GEMINI, OPENAI)
├── pvc.yaml              # Almacenamiento persistente (10Gi)
├── deployment.yaml       # Deployment con 2 réplicas
├── service.yaml          # ClusterIP service
├── ingress.yaml          # Ingress con TLS + WebSocket
├── hpa.yaml              # Auto-scaling (2-10 réplicas)
├── pdb.yaml              # Pod Disruption Budget
├── networkpolicy.yaml    # Políticas de red
├── kustomization.yaml    # Kustomize para patches
├── deploy.sh             # Script de despliegue
└── README.md             # Este archivo
```

## Comandos

### Desplegar

```bash
# Despliegue completo
bash k8s/deploy.sh

# Solo simular (dry-run)
bash k8s/deploy.sh --dry-run

# Ver estado
bash k8s/deploy.sh --status

# Ver logs
bash k8s/deploy.sh --logs

# Eliminar
bash k8s/deploy.sh --delete
```

### Kustomize

```bash
# Aplicar con kustomize
kubectl apply -k k8s/

# Dry-run
kubectl apply -k k8s/ --dry-run=client

# Ver recursos
kubectl kustomize k8s/
```

### Gestión manual

```bash
# Ver pods
kubectl get pods -n audioclass

# Ver servicios
kubectl get svc -n audioclass

# Ver ingress
kubectl get ingress -n audioclass

# Ver logs
kubectl logs -f -l app.kubernetes.io/name=audioclass -n audioclass

# Port forward (acceso local)
kubectl port-forward svc/audioclass-server 8000:80 -n audioclass

# Exec en un pod
kubectl exec -it $(kubectl get pod -n audioclass -l app.kubernetes.io/component=server -o name | head -1) -n audioclass -- /bin/bash
```

## Configuración

### Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `AUDIOCLASS_PORT` | 8000 | Puerto del servidor |
| `AUDIOCLASS_API_KEY` | (vacío) | API key para autenticación |
| `AUDIOCLASS_MAX_UPLOAD_MB` | 200 | Límite de upload en MB |
| `AUDIOCLASS_RATE_LIMIT` | 30 | Rate limit por minuto |
| `AUDIOCLASS_MODEL` | base | Modelo de Whisper |
| `GEMINI_API_KEY` | (vacío) | API key de Google Gemini |
| `OPENAI_API_KEY` | (vacío) | API key de OpenAI |

### Configurar secrets

```bash
# Editar secret.yaml
nano k8s/secret.yaml

# O crear desde comando
kubectl create secret generic audioclass-secrets \
  --from-literal=AUDIOCLASS_API_KEY=tu-api-key \
  --from-literal=GEMINI_API_KEY=tu-gemini-key \
  -n audioclass
```

## Arquitectura

```
                    ┌─────────────────┐
                    │   Ingress      │
                    │   (NGINX)      │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────┴─────┐ ┌─────┴─────┐ ┌─────┴─────┐
        │  Pod 1    │ │  Pod 2    │ │  Pod N    │
        │  AudioClass│ │ AudioClass│ │ AudioClass│
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────┴────────┐
                    │   PersistentVolume│
                    │   (10Gi)         │
                    └─────────────────┘
```

## Auto-scaling

El HorizontalPodAutoscaler (HPA) escala automáticamente:

- **Mínimo**: 2 réplicas
- **Máximo**: 10 réplicas
- **Métricas**: CPU (70%) y Memory (80%)
- **Scale down**: Estabilización 5min, 1 pod/ciclo
- **Scale up**: Estabilización 30s, 2 pods o 100%/ciclo

## Seguridad

- **NetworkPolicy**: Solo permite tráfico desde Ingress y Prometheus
- **Pod Security**: `runAsNonRoot`, `readOnlyRootFilesystem`, `drop ALL capabilities`
- **TLS**: Cert-Manager con Let's Encrypt automático
- **Rate limiting**: 10 req/s por IP con burst 5x
- **HSTS**: Habilitado con 1 año de max-age

## Monitoreo

### Prometheus

El deployment incluye anotaciones para scraping automático:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port: "8000"
prometheus.io/path: "/metrics"
```

### Health checks

- **Startup probe**: 30 intentos, 10s intervalo
- **Liveness probe**: 30s intervalo, 5s timeout
- **Readiness probe**: 10s intervalo, 5s timeout

## Troubleshooting

### Pods no arrancan

```bash
kubectl describe pod -n audioclass -l app.kubernetes.io/name=audioclass
kubectl logs -n audioclass -l app.kubernetes.io/name=audioclass --tail=50
```

### No hay conectividad

```bash
kubectl get ingress -n audioclass
kubectl describe ingress audioclass-ingress -n audioclass
kubectl get events -n audioclass
```

### Performance issues

```bash
# Ver métricas
kubectl top pods -n audioclass
kubectl top nodes

# Ver HPA
kubectl get hpa -n audioclass
kubectl describe hpa audioclass-hpa -n audioclass
```
