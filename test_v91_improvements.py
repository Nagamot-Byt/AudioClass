#!/usr/bin/env python3
"""
test_v91_improvements.py — Pruebas unitarias para las mejoras de AudioClass v9.1:
1. Resiliencia de get_output_dir() en carpetas de solo lectura / fallback
2. Motor de IA local OllamaAdaptationEngine
3. Sistema de internacionalización (i18n) en ES / EN
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import i18n
from audioclass_core import (
    OllamaAdaptationEngine,
    build_adaptation_engine,
    get_output_dir,
)


class TestOutputDirectoryResilience(unittest.TestCase):
    def test_get_output_dir_returns_valid_path(self):
        out_dir = get_output_dir()
        self.assertTrue(os.path.isdir(out_dir))
        self.assertTrue(os.access(out_dir, os.W_OK))

    def test_get_output_dir_fallback_on_readonly(self):
        # Simular que ~/AudioClass_Recordings no es escribible
        with patch("os.makedirs") as mock_makedirs:
            mock_makedirs.side_effect = [OSError(30, "Read-only file system"), None]
            # Resetear estado estático
            import audioclass_core

            audioclass_core._RESOLVED_OUTPUT_DIR = None
            resolved = get_output_dir()
            self.assertTrue(os.path.exists(resolved))


class TestOllamaAdaptationEngine(unittest.TestCase):
    def test_ollama_engine_build(self):
        engine = build_adaptation_engine(
            provider="ollama",
            ollama_url="http://localhost:11434",
            ollama_model="qwen2.5",
        )
        self.assertIsInstance(engine, OllamaAdaptationEngine)
        self.assertEqual(engine.model, "qwen2.5")
        self.assertEqual(engine.host_url, "http://localhost:11434")

    def test_ollama_test_key_offline_connection_error(self):
        engine = OllamaAdaptationEngine("http://127.0.0.1:59999", "qwen2.5")
        ok, msg = engine.test_key()
        self.assertFalse(ok)
        self.assertIn("No se pudo conectar", msg)

    @patch("requests.post")
    def test_ollama_adapt_mock(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Resumen generado por Ollama"}
        mock_post.return_value = mock_resp

        engine = OllamaAdaptationEngine("http://localhost:11434", "qwen2.5")
        res = engine.adapt("Texto de la clase universitaria de prueba", "Resumen Ejecutivo")
        self.assertIn("text", res)
        self.assertEqual(res["text"], "Resumen generado por Ollama")


class TestI18nSystem(unittest.TestCase):
    def test_locales_load_and_translate(self):
        i18n.load_locales()
        i18n.set_language("es")
        self.assertEqual(i18n.t("rec_btn"), "GRABAR MI CLASE")

        i18n.set_language("en")
        self.assertEqual(i18n.t("rec_btn"), "RECORD MY CLASS")

    def test_fallback_on_missing_key(self):
        i18n.set_language("en")
        translated = i18n.t("non_existent_key", default="Default Value")
        self.assertEqual(translated, "Default Value")


if __name__ == "__main__":
    unittest.main()
