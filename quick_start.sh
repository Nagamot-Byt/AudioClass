#!/usr/bin/env bash
# AudioClass v9.1 - Instalador y Lanzador Rapido (Linux/macOS)
set -e

echo "============================================================"
echo "  AudioClass v9.1 - Instalador y Lanzador Rapido"
echo "============================================================"
echo ""

# Detectar Python
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python no encontrado."
    echo ""
    echo "Instala Python 3.12:"
    echo "  macOS:  brew install python@3.12"
    echo "  Ubuntu: sudo apt install python3.12 python3.12-venv"
    echo "  Arch:   sudo pacman -S python"
    exit 1
fi

echo "Python encontrado: $($PYTHON --version)"
echo ""

# Verificar si hay venv
if [ ! -d "venv" ]; then
    echo "[1/4] Creando entorno virtual..."
    $PYTHON -m venv venv
    echo "      Entorno virtual creado."
else
    echo "[1/4] Entorno virtual existente encontrado."
fi

# Activar venv
echo "[2/4] Activando entorno virtual..."
source venv/bin/activate

# Dependencias del sistema (solo Linux)
if [ "$(uname)" = "Linux" ]; then
    echo "      Verificando dependencias del sistema..."
    for pkg in libportaudio2 libsndfile1; do
        if ! dpkg -s "$pkg" &>/dev/null 2>&1; then
            echo "      Instalando $pkg..."
            sudo apt-get install -y -qq "$pkg" 2>/dev/null || true
        fi
    done
fi

# macOS: portaudio
if [ "$(uname)" = "Darwin" ]; then
    if ! command -v brew &>/dev/null; then
        echo "      [AVISO] Homebrew no encontrado. Instalar portaudio manualmente:"
        echo "              brew install portaudio"
    elif ! brew list portaudio &>/dev/null 2>&1; then
        echo "      Instalando portaudio via Homebrew..."
        brew install portaudio
    fi
fi

# Instalar dependencias Python
echo "[3/4] Instalando dependencias (puede tardar 2-5 min)..."
pip install --upgrade pip --quiet
pip install -r requirements_v91.txt --quiet
echo "      Dependencias instaladas."

# Lanzar la app
echo ""
echo "============================================================"
echo "  AudioClass esta listo. Iniciando..."
echo "============================================================"
echo ""
python audioclass_v91.py

echo ""
echo "AudioClass se ha cerrado."
