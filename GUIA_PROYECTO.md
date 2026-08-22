# AudioClass v9.1 - Guia del Proyecto

> **Estado actual**: PRODUCCION (Release v9.1-final publicada)
> **Ultimo commit**: 3a0be3b en main
> **Remoto**: https://github.com/Nagamot-Byt/AudioClass
> **Modulos extraidos**: ui_builder, config_manager, theme, recording_engine, transcription_engines, export_utils

---

## 1. Que es AudioClass

Aplicacion de escritorio para grabar, transcribir y exportar clases universitarias.
Soporta transcripcion local (faster-whisper/openai-whisper) y remota (Gemini/OpenAI API).

**Plataformas**: Windows (exe), Linux (onedir), macOS (onefile)

---

## 2. Estructura del Proyecto

```
# === MODULOS PRINCIPALES ===
audioclass_v91.py              # App principal (GUI customtkinter, ~5100 lineas)
audioclass_core.py             # Nucleo: pipeline de audio, DSP, modelos
audioclass_colab_server_v91.py # Servidor Flask para Colab
optimizar_mic.py               # Optimizador de microfono (Windows COM)

# === MODULOS EXTRAIDOS (refactor v9.2) ===
ui_builder.py                  # Construccion de UI (11 builder functions)
config_manager.py              # Config persistente (load/save/encrypt)
theme.py                       # Tema y paletas WCAG (claro/oscuro)
recording_engine.py            # Mixin de grabacion (audio capture + flush)
transcription_engines.py       # Registro de motores (local/cloud/API)
export_utils.py                # Helpers PDF/DOCX (fmt_timestamp, docx_paragraph)

# === ASSETS ===
assets/
  audioclass_theme.json        # Tema CTk
  DejaVuSans.ttf               # Fuentes para PDF

# === MODELOS ===
models_ct2/tiny/               # Modelo Whisper tiny (CT2)
models_ct2/base/               # Modelo Whisper base (CT2)

# === CI/CD ===
.github/workflows/
  ci.yml                       # CI: 16 tests en ubuntu
  release.yml                  # Release: builds 3 plataformas + AppImage

# === SPECS PYINSTALLER ===
AudioClass_v91.spec            # PyInstaller onedir (Windows)
AudioClass_v91_onefile.spec    # PyInstaller onefile (Windows/macOS)
AudioClass_v91_linux.spec      # PyInstaller onedir Linux (lean)
AudioClass_v91_onefile_linux.spec # PyInstaller onefile Linux (lean)

# === BUILD SCRIPTS ===
desplegar_produccion.sh        # Build completo Windows
build_linux.sh                 # Build Linux
build_mac.sh                   # Build macOS
build.bat                      # Build Windows (doble clic)
build_appimage.sh              # Build AppImage Linux

# === TESTS (16 en suite) ===
run_ci_suite.py                # Suite de tests (16 tests)
test_api_integration.py        # Tests mocked API (Gemini/OpenAI)
test_config_manager.py         # Tests config manager
test_refactored_modules.py     # Tests modulos extraidos
test_code_signing.py           # Test firma authenticode

# === UTILIDADES ===
quick_start.bat                # Inicio rapido Windows (doble clic)
quick_start.sh                 # Inicio rapido Linux/macOS
apply_signpath.sh              # Asistente para aplicar a SignPath
FIRMA_CODIGO.md                # Guia de firma de codigo + SignPath
CODE_SIGNING_POLICY.md         # Politica de firma (req. SignPath)
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
# Suite completa (16 tests)
python run_ci_suite.py

# Test individual
python -m pytest test_privacy_consent.py
python -m pytest test_wcag_contrast.py
python -m pytest test_e2e_ui.py
python -m pytest test_api_integration.py
python -m pytest test_config_manager.py

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
- 16 tests: ui_smoke, ui_v91, wcag, privacy, colab, code_signing, refactored_modules, parallel, export, e2e_ui, stress, v10, lang_auto, watchdog, config_manager, api_integration

### release.yml (3 plataformas + AppImage)
- Se dispara con tag `v*`
- Builds: Windows (onedir+onefile), Linux (onedir split + AppImage), macOS (onefile)
- Publica Release en GitHub con los zips + AppImage + docs legales
- SignPath Foundation: listo para integrar (comentado en workflow)

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
2ae36c1 feat: AppImage build, mocked API tests, SignPath integration, CI suite expanded
3a0be3b fix(pyinstaller): move QA imports out of try/except and rewrite test for PyInstaller 6.x
83fac1d test(exe): verify audio_quality_checker and sound_error_solver in bundled exe
08b1116 test(audio): E2E quality gate - 37 checks for audio quality and transcription blocking
eaa9b8a feat(audio): anti-fallo de calidad y solucionador de errores de sonido
a1b82fd test(mic): add test_mic_detection to CI suite (22 checks)
95f92cf refactor: extract ui_builder.py and add docstrings to 100% of functions
5871429 feat: add SignPath Foundation application helper script
eb17696 refactor: extract recording_engine, transcription_engines, export_utils
40fbef8 feat: theme.py extraction, dependabot, pinned deps, AppImage, code signing
710a2a7 fix: load_config/save_config wrappers use local CONFIG_PATH
```

---

## 9. Edicion Rapida: Que Archivo Tocar

| Quiero cambiar... | Edita... | Notas |
|---|---|---|
| **UI / Botones / Layout** | `ui_builder.py` + `audioclass_v91.py` | 11 builder functions en ui_builder.py |
| **Colores / Tema** | `theme.py` + `assets/audioclass_theme.json` | Paletas WCAG, cambio en caliente |
| **Grabacion de audio** | `recording_engine.py` | Mixin: grabacion, streaming, flusher |
| **Transcripcion local** | `audioclass_core.py` | Pipeline faster_whisper |
| **Transcripcion API** | `audioclass_v91.py` + `transcription_engines.py` | Gemini + OpenAI + registro de motores |
| **Exportacion PDF/DOCX** | `export_utils.py` | Helpers: fmt_timestamp, docx_paragraph |
| **Servidor Colab** | `audioclass_colab_server_v91.py` | Flask app |
| **Optimizador de microfono** | `optimizar_mic.py` | Windows COM |
| **Configuracion persistente** | `config_manager.py` | load/save/encrypt (DPAPI) |
| **Modelos Whisper** | `models_ct2/tiny/` y `models_ct2/base/` | CT2 format |
| **Tests** | `test_*.py` | 16 tests en suite |
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

`audioclass_v91.py` es la app GUI que orquesta todo, delegando la construccion de widgets a `ui_builder.py` (11 builder functions). `audioclass_core.py` es el motor de audio/transcripcion. Los modulos extraidos (`config_manager.py`, `theme.py`, `recording_engine.py`, `transcription_engines.py`, `export_utils.py`) manejan responsabilidades especificas. El server Flask (`audioclass_colab_server_v91.py`) es independiente. Los specs PyInstaller empaquetan todo en un exe autocontenido.

---

## 10. Firma de Codigo

### Estado actual

- **Self-signing**: Implementado en `release.yml` (certificado temporal por build)
- **SignPath Foundation**: Pendiente de solicitud (gratis para open source)
- Docs: `FIRMA_CODIGO.md`, `CODE_SIGNING_POLICY.md`

### Self-signing (ya funciona)

El pipeline de release genera un certificado auto-firmado y firma el exe Windows:

```
release.yml > Build Windows > Self-signing (certificado temporal)
```

Esto **NO** elimina SmartScreen pero garantiza integridad del binario.

### SignPath Foundation (RECOMENDADO)

| Requisito | AudioClass | Estado |
|---|---|---|
| Licencia OSI (MIT) | MIT | OK |
| Sin codigo propietario | Solo OSS | OK |
| Proyecto activo | Commits recientes | OK |
| Release publicada | v9.1-final | OK |
| Documentacion | README + GUIA | OK |
| MFA en GitHub | Configurar | PENDIENTE |
| Code signing policy | `CODE_SIGNING_POLICY.md` | OK |
| Teams GitHub | Crear | PENDIENTE |

### Pasos para aplicar a SignPath

1. **Habilitar MFA** en GitHub (Settings > Password > 2FA)
2. **Crear organizacion** en GitHub (si `Nagamot-Byt` es cuenta personal)
3. **Crear teams**: `maintainers` (authors + reviewers) y `approvers`
4. **Ir a** https://signpath.org > Apply
5. **Vincular repositorio** `Nagamot-Byt/AudioClass`
6. **Esperar** 2-3 semanas de revision
7. **Integrar** `SignPath/signpath-action@v1` en `release.yml`

Ver `FIRMA_CODIGO.md` para instrucciones detalladas.

---

## 11. Proximos Pasos Sugeridos

1. **SignPath Foundation**: Aplicar (gratis) para firma EV real
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
