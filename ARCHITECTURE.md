# AudioClass Architecture Decision Records

## Overview
AudioClass is a desktop application for audio transcription and analysis, built with Python and CustomTkinter. It provides offline transcription using Whisper (via faster-whisper/CTranslate2), cloud adaptation via Gemini/OpenAI, and export to DOCX/PDF.

## ADR-001: Service-Based Architecture

**Status**: Accepted

**Context**: The original `App` class was a god-object (~5,200 lines, 128 methods) inheriting multiple mixins (`MicTestMixin`, `RecordingMixin`, `UpdateDialogMixin`, `ConfigDialogMixin`, `ToastMixin`).

**Decision**: Extract business logic into dedicated service classes in `services/`:
- `TranscriptionService`: owns `LocalWhisperEngine`, `AudioPipeline`, `AdaptationEngine`
- `MicService`: microphone testing and optimization logic (from `MicTestMixin`)
- `RecordingService`: audio recording and buffer management (from `RecordingMixin`)
- `UpdateService`: update checking and dialog logic (from `UpdateDialogMixin`)

`App` now composes these services instead of inheriting mixins.

**Consequences**:
- Separation of concerns: UI logic in `App`, business logic in services
- Testability: services can be unit-tested independently
- Maintainability: smaller, focused modules

## ADR-002: Transcription Backend Abstraction

**Status**: Accepted

**Context**: Need to support multiple transcription backends (openai-whisper, faster-whisper, cloud APIs).

**Decision**: Introduce `TranscriptionBackend` ABC in `transcription_engines.py`. Implementations:
- `LocalWhisperEngine`: wraps faster-whisper (CTranslate2 int8) and openai-whisper fallback
- `CloudColabEngine`: Google Colab integration
- `GeminiAdaptationEngine` / `OpenAIAdaptationEngine`: cloud adaptation

**Consequences**: Easy to add new backends; tests can mock the interface.

## ADR-003: Voice Activity Detection (VAD) in Pipeline

**Status**: Accepted

**Context**: Need to filter silence in real-time transcription/recording.

**Decision**: Add optional VAD to `AudioPipeline.process(vad=False)`. Uses RMS-based threshold (25ms frames, 15th percentile energy threshold). No external dependencies.

**Consequences**:
- Reduces transcription time on silence
- Deterministic with fixed numpy seed
- No external dependencies (silero VAD available as optional future upgrade)

## ADR-004: Server Factory Pattern

**Status**: Accepted

**Context**: Two HTTP servers (`audioclass_server.py`, `audioclass_colab_server_v91.py`) shared significant boilerplate (CORS, logging, routes).

**Decision**: Extract `create_base_app()` in `server_app.py`. Both servers now use this factory.

**Consequences**: DRY, consistent security headers, easier maintenance.

## ADR-005: Configuration Consolidation

**Status**: Accepted

**Context**: Configuration scattered across `config_manager.py`, `config_dialog.py`, `audioclass_v91.py` with aliases (`ac.CONFIG_PATH`, etc.).

**Decision**: Single source of truth in `config_manager.py` with single import block in `audioclass_v91.py`. Backward compatibility via `ac` alias.

## ADR-006: Legacy Code Removal

**Status**: Accepted

**Context**: Directories `First Version/` and `Second Version/` contained ~15,000 lines of dead code.

**Decision**: Deleted. No references found in active codebase.

## ADR-007: Security Hardening

**Status**: Accepted

**Decisions**:
- Default bind `127.0.0.1` (configurable via `AUDIOCLASS_HOST` env)
- Warning banner if `0.0.0.0` explicitly set
- API keys encrypted with DPAPI (Windows) / keyring (Linux)
- Consent flow for recording and AI adaptation
- `validate_export_path` restricts exports to safe directories

## ADR-008: Testing Strategy

**Status**: Accepted

**Approach**:
- Unit tests: `test_core_units.py` (24 tests, synthetic audio)
- Integration tests: `test_integration_v91.py` (7 tests, services/App structure)
- Real model tests: `test_real_models.py` (Whisper tiny + real audio)
- Stress tests: `test_stress_transcripcion.py` (deterministic with fixed seed)
- CI: `run_ci_suite.py` (21 tests, parity guard with workflow)

## ADR-009: Type Checking Strategy

**Status**: Proposed

**Context**: 84 mypy warnings (mostly external library stubs, `windll`, annotations).

**Decision**: mypy in CI as **informative** step (`--ignore-missing-imports`). Blocker conversion blocked on fixing pre-existing warnings.

## ADR-010: VAD in Pipeline

**Status**: Accepted

**Decision**: RMS-based VAD in `AudioPipeline.process(vad=True)`. 25ms frames, 15th percentile threshold. Deterministic with fixed numpy seed.

## Project Structure

```
AudioClass/
├── audioclass_v91.py          # Main App (UI, composition root)
├── audioclass_core.py         # Core engines (AudioPipeline, LocalWhisperEngine, etc.)
├── server_app.py              # Server factory
├── config_manager.py          # Configuration
├── transcription_engines.py   # TranscriptionBackend ABC + implementations
├── services/                  # Extracted services
│   ├── transcription_service.py
│   ├── mic_service.py
│   ├── recording_service.py
│   └── update_service.py
├── config_dialog.py           # Config UI
├── mic_optimizer_ui.py        # Re-exports MicTestMixin
├── recording_engine.py        # Re-exports RecordingMixin
├── update_dialog_ui.py        # Re-exports UpdateDialogMixin
├── theme.py                   # Theming
├── export_utils.py            # DOCX/PDF export
├── test_*.py                  # Test suite (21 CI tests)
├── run_ci_suite.py            # CI runner
├── .github/workflows/ci.yml   # CI pipeline
├── models/                    # Whisper models (gitignored)
├── pyproject.toml             # Dependencies
└── ARCHITECTURE.md            # This document
```

## Glossary

- **CT2**: CTranslate2 (faster-whisper backend)
- **VAD**: Voice Activity Detection
- **RMS**: Root Mean Square (energy measure)
- **DPAPI**: Windows Data Protection API
- **ADR**: Architecture Decision Record
