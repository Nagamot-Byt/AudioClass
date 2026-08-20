# -*- coding: utf-8 -*-
"""test_refactored_modules.py — Tests para los modulos extraidos del monolito.

Valida export_utils, recording_engine y transcription_engines sin
dependencias de GUI.

Patron de exito: REFACTORED_OK
"""
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

passed = 0
failed = 0


def check(name, cond, msg=""):
    global passed, failed
    if cond:
        print(f"  OK   {name}")
        passed += 1
    else:
        print(f"  FAIL {name}: {msg}")
        failed += 1


def test_export_utils():
    print("\n=== export_utils ===")
    from export_utils import fmt_timestamp, export_lines, docx_paragraph, docx_heading, parse_adapt_sections

    # fmt_timestamp
    check("fmt_ts 0", fmt_timestamp(0) == "00:00")
    check("fmt_ts 65", fmt_timestamp(65) == "01:05")
    check("fmt_ts None", fmt_timestamp(None) == "00:00")
    check("fmt_ts 3661", fmt_timestamp(3661) == "61:01")

    # export_lines sin segmentos
    has_ts, lines = export_lines("Hola mundo\nLinea dos")
    check("export_lines no ts", not has_ts)
    check("export_lines 2 lineas", len(lines) == 2)

    # export_lines con segmentos
    segs = [{"start": 0, "end": 5, "text": "Hola"}, {"start": 5, "end": 10, "text": "Mundo"}]
    has_ts, lines = export_lines("Hola Mundo", last_segments=segs)
    check("export_lines con ts", has_ts)
    check("export_lines 2 segs", len(lines) == 2)
    check("export_lines ts val", lines[0][2] == "Hola")

    # export_lines texto vacio
    has_ts, lines = export_lines("")
    check("export_lines vacio", len(lines) >= 1)

    # docx_paragraph
    p = docx_paragraph("Test")
    check("docx_p tiene w:p", "<w:p>" in p)
    check("docx_p tiene texto", "Test" in p)
    h = docx_heading("Titulo")
    check("docx_heading negrita", "<w:b/>" in h)
    check("docx_heading color", "0A1F44" in h)

    # parse_adapt_sections
    txt = "**Resumen Ejecutivo:** La clase explica X\n**Tesis Central:** Y es importante"
    sections = parse_adapt_sections(txt)
    check("parse_adapt 2 secciones", len(sections) == 2)
    check("parse_adapt labels", sections[0][0] == "Resumen Ejecutivo")

    # parse_adapt sin encabezados
    txt2 = "Texto sin encabezados conocidos."
    sections2 = parse_adapt_sections(txt2)
    check("parse_adapt fallback", len(sections2) == 1)


def test_transcription_engines():
    print("\n=== transcription_engines ===")
    from transcription_engines import TRANSCRIPTION_ENGINES, select_engine, get_available_engines

    # Registro
    check("engines 5", len(TRANSCRIPTION_ENGINES) == 5)
    check("engines tiene local", "local" in TRANSCRIPTION_ENGINES)
    check("engines tiene gemini", "gemini" in TRANSCRIPTION_ENGINES)
    check("engines tiene openai", "openai" in TRANSCRIPTION_ENGINES)

    # select_engine local
    cfg = {"mode": "local"}
    key, eng = select_engine(cfg)
    check("select local", key == "local")

    # select_engine gemini con key
    cfg = {"mode": "gemini", "gemini_api_key": "test123"}
    key, eng = select_engine(cfg)
    check("select gemini", key == "gemini")

    # select_engine gemini sin key -> None
    cfg = {"mode": "gemini"}
    key, eng = select_engine(cfg)
    check("select gemini sin key", key is None)

    # select_engine openai con key
    cfg = {"mode": "openai", "openai_api_key": "sk-test"}
    key, eng = select_engine(cfg)
    check("select openai", key == "openai")

    # get_available_engines
    cfg = {"mode": "local", "gemini_api_key": "key"}
    engines = get_available_engines(cfg)
    check("available 5 motores", len(engines) == 5)
    local_avail = [e for e in engines if e[0] == "local"][0]
    check("local available", local_avail[2] is True)
    gemini_avail = [e for e in engines if e[0] == "gemini"][0]
    check("gemini available", gemini_avail[2] is True)


def test_recording_engine():
    print("\n=== recording_engine ===")
    from recording_engine import mic_device_id_for, RecordingMixin, SAMPLE_RATE, CHANNELS

    # mic_device_id_for
    check("mic_device int", mic_device_id_for({"mic_device": 3}) == 3)
    check("mic_device str", mic_device_id_for({"mic_device": "default"}) is None)
    check("mic_device None", mic_device_for_none())
    check("mic_device empty", mic_device_id_for({}) is None)

    # Constants
    check("sample_rate 16k", SAMPLE_RATE == 16000)
    check("channels 1", CHANNELS == 1)

    # Mixin exists
    check("RecordingMixin existe", hasattr(RecordingMixin, "begin_recording"))
    check("RecordingMixin stoprec", hasattr(RecordingMixin, "stoprec"))
    check("RecordingMixin recloop", hasattr(RecordingMixin, "recloop"))


def mic_device_for_none():
    from recording_engine import mic_device_id_for
    return mic_device_id_for(None) is None


def main():
    test_export_utils()
    test_transcription_engines()
    test_recording_engine()

    global passed, failed
    total = passed + failed
    if failed == 0:
        print(f"\nREFACTORED_OK ({passed}/{total})")
    else:
        print(f"\nREFACTORED_FAIL ({passed}/{total}, {failed} fallos)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
