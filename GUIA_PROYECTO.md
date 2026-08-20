# AudioClass v9.1 - Guia del Proyecto

> **Estado actual**: PRODUCCION (Release v9.1-final publicada)
> **Ultimo commit**: fc25a94 en main
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
fc25a94 ci: split Linux tar.xz into 1GB parts for GitHub 2GB asset limit
ce7c809 ci: Linux onedir with lean spec + fix retry loop exit code
c0c766e ci: Linux switched to onedir build (50MB exe + compressed shared libs)
39bf405 ci: Linux uses tar.xz instead of zip (60-70% better compression on ELF)
91c4988 ci: aggressive Linux size reduction - exclude onnx, heavy scipy/matplotlib/PIL
7a6150b ci: fix Linux build - use lean spec excluding faster_whisper data files
4b7efa0 ci: retry loop for Linux/macOS ZIP uploads, verbose size debug
4349289 ci: fix publish-release - delete+recreate, single-file gh upload steps
```

---

## 9. Proximos Pasos Sugeridos

1. **Firma de codigo**: Requiere certificado OV/EV (~200-400 USD/ano)
2. **Auto-arranque**: Implementar en Windows (registry) y macOS (Login Items)
3. **Notificaciones**: Push notifications para updates
4. **Mas idiomas**: Interface en ingles/frances
5. **Tests E2E en Windows**: PyAutoGUI (requiere desktop fisico)

---

## 10. Comandos Rapidos

```bash
# Ver ultimo commit
git log --oneline -1

# Verificar estado
git status -sb

# Compilar Windows
bash desplegar_produccion.sh --with-onedir

# Correr tests
python run_ci_suite.py

# Ver Release en GitHub
# https://github.com/Nagamot-Byt/AudioClass/releases/tag/v9.1-final
```
