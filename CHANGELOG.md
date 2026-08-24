# Changelog

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
