# ============================================================
# AudioClass v9.1 - Dockerfile multi-stage
#
# Ejecuta la app en cualquier Linux sin instalar dependencias.
# Soporte completo: GUI (Xvfb), audio (PulseAudio), modelos.
#
# Uso rapido:
#   docker build -t audioclass .
#   docker run -it --rm \
#     -e DISPLAY=:99 \
#     -v audioclass_config:/root/.config/audioclass \
#     -v audioclass_recordings:/root/AudioClass_Recordings \
#     audioclass
#
# Con audio real (micfono del host):
#   docker run -it --rm \
#     --device /dev/snd \
#     --group-add audio \
#     -e PULSE_SERVER=unix:/run/user/$(id -u)/pulse/native \
#     -v /run/user/$(id -u)/pulse:/run/user/$(id -u)/pulse \
#     -e DISPLAY=$DISPLAY \
#     -v /tmp/.X11-unix:/tmp/.X11-unix \
#     audioclass
#
# Con docker-compose:
#   docker-compose up
# ============================================================

FROM python:3.12-slim AS base

# Evitar prompts interactivos durante build
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen \
    DISPLAY=:99

# ── Dependencias del sistema ──────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Audio
    libportaudio2 \
    portaudio19-dev \
    libsndfile1 \
    # GUI / display
    python3-tk \
    xvfb \
    x11-utils \
    xdotool \
    # OpenGL / graficos
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    # PulseAudio (audio virtual)
    pulseaudio \
    pulseaudio-utils \
    # Utilidades
    curl \
    wget \
    git \
    file \
    && rm -rf /var/lib/apt/lists/*

# ── Crear usuario no-root ─────────────────────────────────
RUN groupadd -r audioclass && useradd -r -g audioclass -G audio \
    -d /app -s /bin/bash audioclass

# ── Directorios de trabajo ────────────────────────────────
WORKDIR /app

# ── Copiar requirements primero (cache de Docker) ────────
COPY requirements_v91.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements_v91.txt

# ── Copiar codigo fuente ──────────────────────────────────
COPY *.py ./
COPY assets/ ./assets/
COPY models_ct2/ ./models_ct2/

# ── Copiar documentos legales ─────────────────────────────
COPY LICENCIA.txt EULA.txt AVISO_DE_PRIVACIDAD.txt \
     TERCEROS_Y_LICENCIAS.md LEEME.txt ./

# ── Permisos ──────────────────────────────────────────────
RUN chown -R audioclass:audioclass /app

# ── Script de inicio ──────────────────────────────────────
COPY docker_entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker_entrypoint.sh

# ── Puerto del servidor Colab (opcional) ──────────────────
EXPOSE 5000

# ── Volume mounts para datos persistentes ─────────────────
# Config: ~/.config/audioclass/
# Recordings: ~/AudioClass_Recordings/
VOLUME ["/root/.config/audioclass", "/root/AudioClass_Recordings"]

# ── Usuario no-root ───────────────────────────────────────
USER audioclass

# ── Healthcheck ───────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sounddevice; print('OK')" || exit 1

ENTRYPOINT ["docker_entrypoint.sh"]
CMD ["python", "audioclass_v91.py"]
