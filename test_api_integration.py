#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_api_integration.py — Tests de integracion con API mocked
=============================================================

Verifica el pipeline completo grabacion -> transcripcion -> adaptacion
sin hacer llamadas reales a la API. Usa unittest.mock para simular
respuestas de Gemini y OpenAI.

Ejecutar: python -m pytest test_api_integration.py -v
"""
import os, sys, json, tempfile, threading, time
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audioclass_core import (
    GeminiAdaptationEngine, OpenAIAdaptationEngine,
    LocalWhisperEngine, CloudColabEngine, AudioPipeline,
)
from config_manager import DEFAULT_CONFIG

# El primer template siempre existe
_FIRST_TEMPLATE = list(GeminiAdaptationEngine.TEMPLATES.keys())[0]


class TestGeminiAPIIntegration:
    """Tests de integracion del motor Gemini con API mocked."""

    def test_adapt_returns_formatted_text(self):
        """Verifica que adapt() devuelve texto formateado con la respuesta mock."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "Resumen de clase: Tema X.\nTesis: Y."}]}
            }]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            engine = GeminiAdaptationEngine("fake-key-123456789", "flash")
            result = engine.adapt("Texto de transcripcion de prueba.", _FIRST_TEMPLATE)

            assert "error" not in result, f"Unexpected error: {result.get('error')}"
            assert "Resumen de clase" in result["text"]
            assert result["provider"] == "Gemini"
            call_args = mock_post.call_args
            assert "generativelanguage.googleapis.com" in call_args[0][0]

    def test_adapt_with_pro_model(self):
        """Verifica que el modelo Pro se usa correctamente."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{
                "content": {"parts": [{"text": "Analisis profundo del tema."}]}
            }]
        }

        with patch("requests.post", return_value=mock_resp):
            engine = GeminiAdaptationEngine("fake-key-123456789", "pro")
            result = engine.adapt("Texto de prueba.", _FIRST_TEMPLATE)
            assert "error" not in result
            assert "Analisis profundo" in result["text"]
            # _model_name returns full model string
            assert "pro" in result["model"]

    def test_adapt_handles_api_error(self):
        """Verifica que errores de API se manejan gracefully."""
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        mock_resp.text = "API key invalid"
        mock_resp.json.return_value = {"error": {"message": "API key invalid"}}

        with patch("requests.post", return_value=mock_resp):
            engine = GeminiAdaptationEngine("invalid-key", "flash")
            result = engine.adapt("Texto.", _FIRST_TEMPLATE)
            assert "error" in result

    def test_adapt_handles_network_error(self):
        """Verifica que errores de red se manejan gracefully."""
        with patch("requests.post", side_effect=Exception("Connection timeout")):
            engine = GeminiAdaptationEngine("fake-key-123456789", "flash")
            result = engine.adapt("Texto.", _FIRST_TEMPLATE)
            assert "error" in result

    def test_adapt_all_templates(self):
        """Verifica que todas las plantillas generan respuesta."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "OK"}]}}]
        }

        with patch("requests.post", return_value=mock_resp):
            engine = GeminiAdaptationEngine("fake-key-123456789", "flash")
            for name in GeminiAdaptationEngine.TEMPLATES:
                result = engine.adapt("Texto de prueba.", name)
                assert "error" not in result, f"Template '{name}' failed: {result}"


class TestOpenAIIntegration:
    """Tests de integracion del motor OpenAI con API mocked."""

    def test_adapt_returns_formatted_text(self):
        """Verifica que adapt() de OpenAI devuelve texto formateado."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": "Resumen OpenAI: Clase sobre topicos avanzados."}
            }]
        }

        with patch("requests.post", return_value=mock_resp) as mock_post:
            engine = OpenAIAdaptationEngine("fake-openai-key-12345", "mini")
            result = engine.adapt("Texto de transcripcion.", _FIRST_TEMPLATE)

            assert "error" not in result, f"Unexpected error: {result.get('error')}"
            assert "Resumen OpenAI" in result["text"]
            assert result["provider"] == "OpenAI"
            call_args = mock_post.call_args
            assert "api.openai.com" in call_args[0][0]

    def test_adapt_gpt4o_model(self):
        """Verifica que GPT-4o se usa correctamente."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Analisis GPT-4o."}}]
        }

        with patch("requests.post", return_value=mock_resp):
            engine = OpenAIAdaptationEngine("fake-key-12345", "gpt4o")
            result = engine.adapt("Texto.", _FIRST_TEMPLATE)
            assert "error" not in result
            assert "gpt-4o" in result["model"]

    def test_adapt_handles_error(self):
        """Verifica que errores de OpenAI se manejan."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}

        with patch("requests.post", return_value=mock_resp):
            engine = OpenAIAdaptationEngine("bad-key", "mini")
            result = engine.adapt("Texto.", _FIRST_TEMPLATE)
            assert "error" in result

    def test_adapt_all_templates(self):
        """Verifica que todas las plantillas funcionan con OpenAI."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "OK"}}]
        }

        with patch("requests.post", return_value=mock_resp):
            engine = OpenAIAdaptationEngine("fake-key-12345", "mini")
            for name in OpenAIAdaptationEngine.TEMPLATES:
                result = engine.adapt("Texto de prueba.", name)
                assert "error" not in result, f"Template '{name}' failed: {result}"


class TestTranscriptionPipeline:
    """Tests del pipeline de transcripcion local."""

    def test_local_engine_instantiation(self):
        """Verifica que el motor local se instancia correctamente."""
        engine = LocalWhisperEngine(model_name="tiny")
        assert engine.model_name == "tiny"

    def test_cloud_engine_instantiation(self):
        """Verifica que el motor cloud se instancia correctamente."""
        engine = CloudColabEngine(url="http://localhost:8080", api_key="test")
        assert engine.url == "http://localhost:8080"

    def test_engine_has_transcribe(self):
        """Verifica que los motores tienen el metodo transcribe."""
        assert hasattr(LocalWhisperEngine, "transcribe")
        assert hasattr(CloudColabEngine, "transcribe")


class TestExportPipeline:
    """Tests del pipeline de exportacion."""

    def test_pipeline_instantiation(self):
        """Verifica que AudioPipeline se instancia correctamente."""
        pipeline = AudioPipeline()
        assert pipeline.profile is not None
        assert isinstance(pipeline.profile, dict)

    def test_docx_helpers_exist(self):
        """Verifica que los helpers de DOCX existen y son funcionales."""
        from export_utils import fmt_timestamp, parse_adapt_sections

        assert fmt_timestamp(65.0) == "01:05"
        assert fmt_timestamp(0.0) == "00:00"
        assert fmt_timestamp(3661.0) == "61:01"

        sections = parse_adapt_sections("TEMA\nContenido aqui\n\nTESIS\nOtro texto")
        assert len(sections) >= 1


class TestConfigPipeline:
    """Tests del pipeline de configuracion completa."""

    def test_providers_defaults(self):
        """Verifica que los defaults de proveedores existen."""
        assert "gemini_api_key" in DEFAULT_CONFIG
        assert "gemini_model" in DEFAULT_CONFIG
        assert "openai_api_key" in DEFAULT_CONFIG
        assert "openai_model" in DEFAULT_CONFIG
        assert "adapt_provider" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["adapt_provider"] == "gemini"
        assert DEFAULT_CONFIG["openai_model"] == "mini"
        assert DEFAULT_CONFIG["gemini_model"] == "flash"

    def test_config_roundtrip(self):
        """Verifica que guardar y cargar config preserva campos no-secret."""
        from config_manager import load_config, save_config

        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = os.path.join(tmpdir, "test_config.json")
            original = DEFAULT_CONFIG.copy()
            original["adapt_provider"] = "openai"
            original["local_model"] = "small"

            with patch("config_manager.CONFIG_PATH", cfg_path):
                save_config(original)
                loaded = load_config()

            assert loaded["adapt_provider"] == "openai"
            assert loaded["local_model"] == "small"


class TestUIBuilderIntegration:
    """Tests de integracion del ui_builder."""

    def test_all_builder_functions_exist(self):
        """Verifica que todas las funciones builder existen y son callable."""
        from ui_builder import (
            build_sidebar, build_header, build_easy_mode, build_controls,
            build_config_bar, build_progress, build_waveform, build_adapt,
            build_transcription, build_footer, build_vu_meter,
        )
        funcs = [build_sidebar, build_header, build_easy_mode, build_controls,
                 build_config_bar, build_progress, build_waveform, build_adapt,
                 build_transcription, build_footer, build_vu_meter]
        for f in funcs:
            assert callable(f), f"{f.__name__} is not callable"

    def test_builder_module_docstring(self):
        """Verifica que ui_builder tiene docstring de modulo."""
        import ui_builder
        assert ui_builder.__doc__ is not None
        assert "ui_builder" in ui_builder.__doc__


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pytest
    rc = pytest.main([__file__, "-v", "--tb=line", "-q"])
    if rc == 0:
        print("API_INTEGRATION_OK")
    sys.exit(rc)
