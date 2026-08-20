# AudioClass v9.1 — Edicion Academica Profesional

![Version](https://img.shields.io/badge/version-9.1-final-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12+-yellow)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![CI](https://img.shields.io/github/actions/workflow/status/Nagamot-Byt/AudioClass/ci.yml?label=CI)

> **Graba, transcribe y exporta tus clases universitarias con IA.**
> Todo se controla con botones. Todo se guarda solo.

---

## Caracteristicas

- **Grabacion de audio** con nivel de microfono en tiempo real y diagnostico automatico
- **Transcripcion local** (faster-whisper / openai-whisper) — funciona sin internet
- **Transcripcion en la nube** (Gemini / OpenAI API) — para calidad profesional
- **Analisis academico con IA** — resumen ejecutivo, tesis, pilares, evidencia
- **Exportacion PDF y DOCX** — con timestamps, numeracion y diseno profesional
- **Selector de microfono** — graba con el microfono que elijas
- **Modo Facil** — Grabar > Procesar > Transcribir > Analizar (1 boton)
- **Asistente de primer arranque** — configura todo en tu primera ejecucion
- **Multiidioma** — deteccion automatica de idioma (espanol, ingles, frances, portugues)

---

## Instalacion

### Windows (recomendado)

1. Descarga `AudioClass_v9.1_COMPLETA.zip` desde [Releases](https://github.com/Nagamot-Byt/AudioClass/releases/tag/v9.1-final)
2. Descomprime en la carpeta que prefieras
3. Ejecuta `AudioClass COMPLETA v9.1.exe`

> Primera ejecucion: el asistente te guiara para configurar microfono y preferencias.

### Linux

```bash
# Descargar las 3 partes
# Reconstruir:
cat AudioClass_v9.1_LINUX_part_* > AudioClass_v9.1_LINUX.tar.xz
# Extraer:
tar xJf AudioClass_v9.1_LINUX.tar.xz
# Ejecutar:
./AudioClass/AudioClass
```

### macOS

1. Descarga `AudioClass_v9.1_MACOS.zip` desde [Releases](https://github.com/Nagamot-Byt/AudioClass/releases/tag/v9.1-final)
2. Descomprime y ejecuta el binario

### Desde codigo fuente

```bash
git clone https://github.com/Nagamot-Byt/AudioClass.git
cd AudioClass
pip install -r requirements_v91.txt
python audioclass_v91.py
```

---

## Compilacion

```bash
# Windows (build completo con tests)
bash desplegar_produccion.sh --with-onedir

# Linux
bash build_linux.sh --onedir

# macOS
bash build_mac.sh --onefile
```

---

## Tests

```bash
# Suite completa (13 tests)
python run_ci_suite.py

# Test individual
python -m pytest test_wcag_contrast.py -v
```

---

## Estructura del Proyecto

```
audioclass_v91.py              # App principal (GUI customtkinter)
audioclass_core.py             # Nucleo: pipeline de audio, DSP, modelos
audioclass_colab_server_v91.py # Servidor Flask para Colab
config_manager.py              # Configuracion persistente (cifrada)
export_utils.py                # Utilidades de exportacion PDF/DOCX
optimizar_mic.py               # Optimizador de microfono

assets/audioclass_theme.json   # Tema de la interfaz
models_ct2/tiny/               # Modelo Whisper tiny
models_ct2/base/               # Modelo Whisper base

.github/workflows/ci.yml       # CI: 13 tests en ubuntu
.github/workflows/release.yml  # Release: builds 3 plataformas
```

---

## Documentacion Legal

| Archivo | Contenido |
|---|---|
| `LICENCIA.txt` | MIT (autor: Daniel Perez) |
| `EULA.txt` | Acuerdo de licencia de usuario final |
| `AVISO_DE_PRIVACIDAD.txt` | Aviso de privacidad (LFPDPPP) |
| `TERCEROS_Y_LICENCIAS.md` | Licencias de dependencias |

---

## Licencia

MIT License. Ver `LICENCIA.txt` para detalles.

---

**Desarrollado con dedicacion por Daniel Perez**
