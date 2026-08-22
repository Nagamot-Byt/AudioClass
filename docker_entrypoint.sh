#!/usr/bin/env bash
# docker_entrypoint.sh — Inicializa audio virtual y lanza AudioClass
set -e

echo "============================================================"
echo "  AudioClass v9.1 - Docker Container"
echo "============================================================"

# ── Iniciar Xvfb (display virtual) ────────────────────────
if ! pgrep -x Xvfb > /dev/null 2>&1; then
    echo "[1/4] Iniciando display virtual (Xvfb)..."
    Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
    sleep 1
    export DISPLAY=:99
    echo "      Display virtual listo."
else
    echo "[1/4] Xvfb ya esta corriendo."
    export DISPLAY=:99
fi

# ── Iniciar PulseAudio (audio virtual) ────────────────────
if ! pgrep -x pulseaudio > /dev/null 2>&1; then
    echo "[2/4] Iniciando PulseAudio..."
    pulseaudio --start --exit-idle-time=-1 --daemonize=yes 2>/dev/null || true
    sleep 1
    echo "      PulseAudio listo."
else
    echo "[2/4] PulseAudio ya esta corriendo."
fi

# ── Verificar audio ───────────────────────────────────────
echo "[3/4] Verificando dispositivos de audio..."
python -c "
import sounddevice as sd
devices = sd.query_devices()
print(f'      Dispositivos encontrados: {len(devices)}')
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        print(f'      [{i}] {d[\"name\"]} (input, {d[\"max_input_channels\"]}ch)')
" 2>/dev/null || echo "      [AVISO] No se pudieron listar dispositivos de audio."

# ── Crear directorios de datos ─────────────────────────────
echo "[4/4] Preparando directorios..."
mkdir -p ~/.config/audioclass
mkdir -p ~/AudioClass_Recordings

echo ""
echo "============================================================"
echo "  AudioClass listo. Iniciando..."
echo "============================================================"
echo ""

# ── Ejecutar el comando ───────────────────────────────────
exec "$@"
