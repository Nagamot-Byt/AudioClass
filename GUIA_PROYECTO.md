# AudioClass v9.1 - Guia del Proyecto

> **Estado actual**: PRODUCCION (Release v9.1-final publicada)
> **Ultimo commit**: 23c9a47 en main
> **Remoto**: https://github.com/Nagamot-Byt/AudioClass

---

## 1. Que es AudioClass

Aplicacion de escritorio para grabar, transcribir y exportar clases universitarias.
Soporta transcripcion local (faster-whisper/openai-whisper) y remota (Gemini/OpenAI API).

**Plataformas**: Windows (exe), Linux (onedir), macOS (onefile)

---

## 2. Estructura del Proyecto

```
audioclass_v91.py              # App principal (GUI customtkinter)
audioclass_core.py             # Nucleo: pipeline de audio, DSP, modelos
audioclass_colab_server_v91.py # Servidor Flask para Colab
optimizar_mic.py               # Optimizador de microfono (Windows COM)

assets/
  audioclass_theme.json        # Tema CTk
  DejaVuSans.ttf               # Fuentes para PDF

models_ct2/tiny/               # Modelo Whisper tiny (CT2)
models_ct2/base/               # Modelo Whisper base (CT2)

.github/workflows/
  ci.yml                       # CI: 13 tests en ubuntu
  release.yml                  # Release: builds 3 plataformas + publish

AudioClass_v91.spec            # PyInstaller onedir (Windows)
AudioClass_v91_onefile.spec    # PyInstaller onefile (Windows/macOS)
AudioClass_v91_linux.spec      # PyInstaller onedir Linux (lean)
AudioClass_v91_onefile_linux.spec # PyInstaller onefile Linux (lean)

desplegar_produccion.sh        # Build completo Windows
build_linux.sh                 # Build Linux
build_mac.sh                   # Build macOS
build.bat                      # Build Windows (doble clic)

run_ci_suite.py                # Suite de tests (13 tests)
```

---

## 3. Como Compilar

### Windows (local)
```bash
# Build completo (tests + exe + zip)
bash desplegar_produccion.sh --with-onedir

# Solo exe (sin tests)
bash desplegar_produccion.sh --skip-tests
```

### Linux
```bash
bash build_linux.sh --onefile   # exe unico (~3GB, split para GitHub)
bash build_linux.sh --onedir    # carpeta (~2.4GB, recomendado)
```

### macOS
```bash
bash build_mac.sh --onefile
```

### Reinstalar dependencias
```bash
pip install -r requirements_v91.txt
pip install pyinstaller
```

---

## 4. Tests

```bash
# Suite completa (13 tests)
python run_ci_suite.py

# Test individual
python -m pytest test_privacy_consent.py
python -m pytest test_wcag_contrast.py
python -m pytest test_e2e_ui.py

# E2E headless (4 escenarios)
xvfb-run -a python audioclass_v91.py --e2e-ui wizard
xvfb-run -a python audioclass_v91.py --e2e-ui config
xvfb-run -a python audioclass_v91.py --e2e-ui widgets
xvfb-run -a python audioclass_v91.py --e2e-ui mic
```

---

## 5. CI/CD

### ci.yml (ubuntu)
- Corre en cada push/PR
- 13 tests: compile, ui_smoke, wcag, privacy, colab, parallel, export, e2e_ui, stress, v10, lang_auto, watchdog, benchmark

### release.yml (3 plataformas)
- Se dispara con tag `v*`
- Builds: Windows (onedir+onefile), Linux (onedir split), macOS (onefile)
- Publica Release en GitHub con los 3 zips + docs legales

---

## 6. Release v9.1-final

| Asset | Plataforma | Tamano |
|---|---|---|
| AudioClass_v9.1_COMPLETA.zip | Windows | 569MB |
| AudioClass_v9.1_LINUX_part_00 | Linux (1/3) | 1024MB |
| AudioClass_v9.1_LINUX_part_01 | Linux (2/3) | 1024MB |
| AudioClass_v9.1_LINUX_part_02 | Linux (3/3) | 362MB |
| AudioClass_v9.1_MACOS.zip | macOS | 520MB |

**Para Linux**:
```bash
cat AudioClass_v9.1_LINUX_part_* > AudioClass_v9.1_LINUX.tar.xz
tar xJf AudioClass_v9.1_LINUX.tar.xz
./AudioClass/AudioClass
```

---

## 7. Documentacion Legal

| Archivo | Contenido |
|---|---|
| LICENCIA.txt | MIT (autor: Daniel Perez) |
| EULA.txt | Acuerdo de licencia de usuario final |
| AVISO_DE_PRIVACIDAD.txt | Aviso de privacidad (LFPDPPP) |
| TERCEROS_Y_LICENCIAS.md | Licencias de dependencias |
| NOTA_RELEASE.md | Notas del Release v9.1-final |

---

## 8. Commits Recientes (orden cronologico)

```
23c9a47 doc: enhance GUIA_PROYECTO.md with quick-edit guide and architecture map
5024c38 doc: add GUIA_PROYECTO.md for easy project re-engagement
fc25a94 ci: split Linux tar.xz into 1GB parts for GitHub 2GB asset limit
ce7c809 ci: Linux onedir with lean spec + fix retry loop exit code
c0c766e ci: Linux switched to onedir build (50MB exe + compressed shared libs)
```

---

## 9. Edicion Rapida: Que Archivo Tocar

| Quiero cambiar... | Edita... | Notas |
|---|---|---|
| **UI / Botones / Layout** | `audioclass_v91.py` | Clase `App` — casi todo esta ahi |
| **Colores / Tema** | `assets/audioclass_theme.json` | Paleta CTk, cambio en caliente |
| **Grabacion de audio** | `audioclass_v91.py` (metodo `_start_recording`) | Usa pyaudio |
| **Transcripcion local** | `audioclass_core.py` | Pipeline faster_whisper |
| **Transcripcion API** | `audioclass_v91.py` (metodo `_transcribe_gemini` / `_transcribe_openai`) | Endpoints Gemini y OpenAI |
| **Exportacion PDF/DOCX** | `audioclass_v91.py` (metodo `_export_pdf`, `_export_docx`) | Usa fpdf2 y python-docx |
| **Servidor Colab** | `audioclass_colab_server_v91.py` | Flask app |
| **Optimizador de microfono** | `optimizar_mic.py` | Windows COM |
| **Configuracion persistente** | `audioclass_v91.py` (constante `CONFIG_PATH`) | JSON en ~/AudioClass_Recordings |
| **Modelos Whisper** | `models_ct2/tiny/` y `models_ct2/base/` | CT2 format |
| **Tests** | `test_*.py` | 13 tests en suite |
| **CI/CD** | `.github/workflows/ci.yml` y `release.yml` | GitHub Actions |
| **Build Windows** | `desplegar_produccion.sh` + `AudioClass_v91_onefile.spec` | |
| **Build Linux** | `build_linux.sh` + `AudioClass_v91_linux.spec` | |
| **Build macOS** | `build_mac.sh` + `AudioClass_v91_onefile.spec` | |
| **Documentos legales** | `LICENCIA.txt`, `EULA.txt`, `AVISO_DE_PRIVACIDAD.txt` | |

### Flujo tipico de edicion

```bash
# 1. Clonar / abrir la carpeta
cd "AudioClass"

# 2. Instalar dependencias
pip install -r requirements_v91.txt

# 3. Editar el codigo
# ... (ver tabla arriba)

# 4. Probar en vivo (sin compilar)
python audioclass_v91.py

# 5. Correr tests para no romper nada
python run_ci_suite.py

# 6. Compilar exe (opcional)
bash desplegar_produccion.sh --skip-tests

# 7. Commitear
git add -A && git commit -m "descripcion"
git push origin main
```

### Agregar un nuevo proveedor de IA

1. Busca en `audioclass_v91.py` el patron `_transcribe_gemini` / `_transcribe_openai`
2. Duplica uno de esos metodos y adapta el endpoint + payload
3. Registra el proveedor en el diccionario `TRANSCRIPTION_ENGINES` (seccion de configuracion)
4. Añade el toggle en Configuracion (metodo `_build_config_dialog`)
5. Agrega un test en `test_adapt_engines.py`

### Leer logs de CI cuando falla

```bash
# Ver el ultimo run
gh run list --limit 3

# Ver logs de un run
gh run view <run-id> --log-failed

# Descargar logs completos
gh run view <run-id> --log > ci_logs.txt
```

### Arquitectura en una linea

`audioclass_v91.py` es la app GUI que orquesta todo. `audioclass_core.py` es el motor de audio/transcripcion. El server Flask (`audioclass_colab_server_v91.py`) es independiente y corre por separado. Los specs PyInstaller empaquetan todo en un exe autocontenido.

---

## 10. Proximos Pasos Sugeridos

1. **Firma de codigo**: Requiere certificado OV/EV (~200-400 USD/ano)
2. **Auto-arranque**: Implementar en Windows (registry) y macOS (Login Items)
3. **Notificaciones**: Push notifications para updates
4. **Mas idiomas**: Interface en ingles/frances
5. **Tests E2E en Windows**: PyAutoGUI (requiere desktop fisico)

---

## 11. Comandos Rapidos

```bash
# Ver ultimo commit
git log --oneline -1

# Verificar estado
git status -sb

# Compilar Windows
bash desplegar_produccion.sh --with-onedir

# Correr tests
python run_ci_suite.py

# Selftest del exe (transcripcion real)
./"AudioClass COMPLETA v9.1.exe" --selftest-transcribe tts_clase.wav salida.txt progreso.txt

# Ver CI en GitHub
git log --oneline -3 && gh run list --limit 3

# Ver Release en GitHub
# https://github.com/Nagamot-Byt/AudioClass/releases/tag/v9.1-final
```
