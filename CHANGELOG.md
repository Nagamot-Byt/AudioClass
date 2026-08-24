# Changelog

## [9.1.2] - 2026-08-24

### Security
- **Path traversal protection**: `validate_export_path()` en `export_utils.py` bloquea paths con `..`, `~`, o escapes fuera del directorio permitido
- Integrado en `_pdf()` y `_export_docx()` — valida el path después del file dialog
- Tests: 12 tests de seguridad en `test_security_audit.py`

### Added
- **`app_metrics.py`**: Módulo de métricas de uso con formato Prometheus-compatible (`to_prometheus_text()`)
- **`config_backup.py`**: Backup/restore de configuración con metadata (versión, timestamp, app version)
- **`PRIVACY.md`**: Política de privacidad declarando manejo de datos de audio y servicios externos
- **`NOTICE`**: Licencias de terceros para todas las dependencias principales
- **`test_integration_mocks.py`**: 35 tests de integración con mocks de APIs (AI providers, update checker, config, theme, plugins, i18n, metrics, backup)
- **`test_security_audit.py`**: 16 tests de auditoría (path traversal, hardcoded credentials, config integrity)
- **CI security job**: Bandit SAST scan + Safety dependency check + artifact upload
- **CI audit-tests job**: Tests de seguridad automatizados

### Architecture
- **UI extraction**: `_show_toast` extraído a `toast_ui.py` (ToastMixin, 231 líneas)
- **UI extraction**: `_show_update_dialog` + `_format_release_notes` + `_insert_formatted_notes` extraídos a `update_dialog_ui.py` (UpdateDialogMixin, 329 líneas)
- `audioclass_v91.py` reducido de 5604 → 5208 líneas (-396, -7%)
- App class ahora hereda de: ToastMixin, UpdateDialogMixin, ConfigDialogMixin, MicTestMixin

### Improved
- `export_utils.py`: Type hints completos con `from __future__ import annotations`
- `app_metrics.py`: Type hints completos en todas las funciones públicas
- Ruff linting: 5 unused imports eliminados automáticamente

## [9.1.1] - 2026-08-24

### Fixed
- **Linux recording pipeline**: `recording_engine.py` importaba `sounddevice` sin try/except, causando crash si PortAudio no está instalado
- **Linux mic device resolution**: `mic_device_id_for()` solo aceptaba IDs numéricos; ahora resuelve por nombre ("pulse", "pipewire", "default") con búsqueda exacta y parcial case-insensitive
- **Waveform widget import**: `audioclass_v91.py` importaba `waveform_widget` sin try/except, causando crash en binarios compilados si el módulo falta
- **Linux PyInstaller spec**: 5 hiddenimports faltantes (`template_plugins`, `plugin_manager_ui`, `waveform_widget`, `locales`, `locales.i18n`)
- **Update dialog crash**: `_show_update_dialog` pasaba `corner_radius=8` pero `_frame()` ya lo fija en 12 → TypeError
- **Formatted notes crash**: `_insert_formatted_notes` usaba variable local `top` del caller sin recibirla como parámetro → NameError

### Added
- `launch_linux.sh`: lanzador un clic que verifica dependencias (Python, PortAudio, tkinter, PulseAudio) y ejecuta la app desde binario, AppImage o source
- Verificación E2E del pipeline completo: device resolution → check_input_settings → mic probe → recording → WAV save

## [9.1] - 2026-08-20

### Added
- Selector de microfono en Configuracion y Asistente de primer arranque
- Modo headless `--e2e-ui` con 4 escenarios (wizard, config, widgets, mic)
- Segundo proveedor de IA: OpenAI (GPT-4o-mini / GPT-4o)
- Selector de proveedor de IA en Configuracion (Gemini / OpenAI)
- Builds multiplataforma: Windows (onefile + onedir), Linux (onedir split), macOS (onefile)
- CI completo con 13 tests automatizados
- Documentos legales: LICENCIA.txt, EULA.txt, AVISO_DE_PRIVACIDAD.txt, TERCEROS_Y_LICENCIAS.md
- GUIA_PROYECTO.md con guia de edicion rapida
- Nota de release profesional (NOTA_RELEASE.md)

### Fixed
- Alucinaciones de Whisper: el selftest detecta frases plantilla
- Contraste WCAG AA en todos los botones
- Timeout del reporter de progreso paralelo (ultimo mensaje puede ser viejo)
- Upload de assets grandes en GitHub Releases (Linux split en partes <1GB)

### Changed
- Refactor de config_manager.py y export_utils.py (separados del monolito)
- Tipografia unificada en toda la interfaz
- Headers de seguridad en el servidor Colab
- Emojis eliminados de todo el codigo fuente

## [9.0] - 2026-07-30

### Added
- Transcripcion local con faster-whisper (CT2 format)
- Pipeline de audio profesional con 4 perfiles preconfigurados
- Prompt academico de élite: filtro cognitivo con identificacion de orador
- Modo Facil: Grabar > Procesar > Transcribir > Analizar
- Exportacion PDF y DOCX con timestamps y diseno profesional
- Optimizador de microfono (Windows COM)
- Asistente de primer arranque

### Fixed
- PyInstaller bundle: todos los modelos y dependencias empaquetados correctamente
- Exclusion de modulos que rompian scipy (unittest, pydoc)

## [8.0] - 2026-07-15

### Added
- Transcripcion en la nube con Gemini API (Google AI Studio)
- Adaptacion inteligente: analisis academico automatico
- Exportacion a Google Docs
- Servidor Flask para Colab

### Changed
- Migracion de whisper original a faster-whisper (CT2)
