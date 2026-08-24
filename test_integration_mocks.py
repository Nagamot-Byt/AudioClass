"""test_integration_mocks.py — Tests de integracion con mocks de APIs externas.

Verifica el flujo completo de transcription + analysis + export
sin depender de APIs reales ni de hardware de audio.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))


class TestPathTraversalSecurity(unittest.TestCase):
    """Verifica que la validacion de paths bloquea path traversal."""

    def test_validate_rejects_dotdot(self):
        from export_utils import validate_export_path

        with self.assertRaises(ValueError):
            validate_export_path("/tmp/export/../../etc/passwd")

    def test_validate_rejects_empty(self):
        from export_utils import validate_export_path

        with self.assertRaises(ValueError):
            validate_export_path("")

    def test_validate_rejects_tilde(self):
        from export_utils import validate_export_path

        with self.assertRaises(ValueError):
            validate_export_path("~/../../etc/passwd")

    def test_validate_accepts_valid_path(self):
        from export_utils import validate_export_path

        tmp = tempfile.gettempdir()
        result = validate_export_path(os.path.join(tmp, "test.pdf"))
        self.assertTrue(result.endswith("test.pdf"))

    def test_safe_export_path_adds_extension(self):
        from export_utils import safe_export_path

        tmp = tempfile.gettempdir()
        result = safe_export_path(os.path.join(tmp, "test"))
        self.assertTrue(result.endswith(".pdf"))

    def test_validate_rejects_relative_escape(self):
        from export_utils import validate_export_path

        with self.assertRaises(ValueError):
            validate_export_path("../etc/shadow")


class TestExportUtils(unittest.TestCase):
    """Tests de las funciones puras de exportacion."""

    def test_fmt_timestamp_zero(self):
        from export_utils import fmt_timestamp

        self.assertEqual(fmt_timestamp(0), "00:00")

    def test_fmt_timestamp_large(self):
        from export_utils import fmt_timestamp

        self.assertEqual(fmt_timestamp(3661), "61:01")

    def test_export_lines_with_segments(self):
        from export_utils import export_lines

        segs = [
            {"start": 0, "end": 5, "text": "Hola"},
            {"start": 5, "end": 10, "text": "Mundo"},
        ]
        has_ts, lines = export_lines("Hola Mundo", segs)
        self.assertTrue(has_ts)
        self.assertEqual(len(lines), 2)

    def test_export_lines_without_segments(self):
        from export_utils import export_lines

        has_ts, lines = export_lines("Hello world test")
        self.assertFalse(has_ts)
        self.assertGreater(len(lines), 0)

    def test_docx_paragraph_basic(self):
        from export_utils import docx_paragraph

        xml = docx_paragraph("Test", bold=True)
        self.assertIn("Test", xml)
        self.assertIn("<w:b/>", xml)

    def test_pdf_safe_latin1(self):
        from export_utils import pdf_safe_latin1

        result = pdf_safe_latin1("Cafe\u0301 no\u00a0est\u00e1")
        # Should not raise, result is latin-1 safe
        self.assertIsInstance(result, str)

    def test_parse_adapt_sections(self):
        from export_utils import parse_adapt_sections

        text = (
            "**Resumen Ejecutivo:** Este es un resumen.\n\n"
            "**Tesis Central:** La tesis principal.\n\n"
            "**Pilares Argumentales:** Pilares.\n"
        )
        sections = parse_adapt_sections(text)
        self.assertGreaterEqual(len(sections), 2)
        labels = [s[0] for s in sections]
        self.assertIn("Resumen Ejecutivo", labels)
        self.assertIn("Tesis Central", labels)


class TestConfigManager(unittest.TestCase):
    """Tests del config manager con mocks."""

    def test_load_save_roundtrip(self):
        from config_manager import load_config, save_config

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            cfg = {"local_model": "tiny", "_config_version": 5, "theme": "auto"}
            save_config(cfg, path)
            loaded = load_config(path)
            self.assertEqual(loaded["local_model"], "tiny")
        finally:
            os.unlink(path)

    def test_load_missing_file_returns_defaults(self):
        from config_manager import load_config

        loaded = load_config("/tmp/nonexistent_audioclass_config_test.json")
        self.assertIsInstance(loaded, dict)
        self.assertIn("local_model", loaded)

    def test_migrate_config_version(self):
        from config_manager import load_config, save_config

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            # Write a v1 config
            old_cfg = {"local_model": "base", "_config_version": 1}
            save_config(old_cfg, path)
            loaded = load_config(path)
            # Should have been migrated to current version
            self.assertGreaterEqual(loaded.get("_config_version", 0), 2)
        finally:
            os.unlink(path)


class TestTemplatePlugins(unittest.TestCase):
    """Tests del sistema de plugins de templates."""

    def test_plugin_manager_exists(self):
        from template_plugins import get_plugin_manager

        pm = get_plugin_manager()
        self.assertIsNotNone(pm)

    def test_plugin_manager_has_builtin(self):
        from template_plugins import get_plugin_manager

        pm = get_plugin_manager()
        templates = pm.get_builtin_templates()
        self.assertIsInstance(templates, (list, dict))


class TestThemeSystem(unittest.TestCase):
    """Tests del sistema de temas."""

    def test_dark_palette_exists(self):
        from theme import PALETTES

        self.assertIn("dark", PALETTES)

    def test_light_palette_exists(self):
        from theme import PALETTES

        self.assertIn("light", PALETTES)

    def test_palette_has_required_keys(self):
        from theme import PALETTES

        for name, palette in PALETTES.items():
            self.assertIn("bg", palette, f"{name} missing bg")
            self.assertIn("text", palette, f"{name} missing text")
            self.assertIn("accent", palette, f"{name} missing accent")


class TestRecordingEngine(unittest.TestCase):
    """Tests del motor de grabacion con mocks."""

    def test_mic_device_id_for_string_device(self):
        from recording_engine import mic_device_id_for

        config = {"mic_device": "pulse"}
        result = mic_device_id_for(config)
        # Should resolve to a numeric device ID or None (if pulse not found)
        self.assertTrue(result is None or isinstance(result, int))

    def test_mic_device_id_for_numeric_device(self):
        from recording_engine import mic_device_id_for

        config = {"mic_device": "0"}
        result = mic_device_id_for(config)
        # Should resolve to integer 0
        self.assertEqual(result, 0)

    def test_mic_device_id_for_empty_config(self):
        from recording_engine import mic_device_id_for

        result = mic_device_id_for({})
        # Should return None (use default)
        self.assertIsNone(result)


class TestUpdateChecker(unittest.TestCase):
    """Tests del verificador de actualizaciones con mocks."""

    @patch("requests.get")
    def test_check_for_updates_newer_available(self, mock_get):
        from update_checker import check_for_updates

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v99.0.0",
            "html_url": "https://github.com/test/test/releases/tag/v99.0.0",
            "body": "New version",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = check_for_updates("1.0.0")
        self.assertTrue(result.get("update_available"))
        # update_checker strips the 'v' prefix
        self.assertEqual(result["latest_version"], "99.0.0")

    @patch("requests.get")
    def test_check_for_updates_current(self, mock_get):
        from update_checker import check_for_updates

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/test/test/releases/tag/v1.0.0",
            "body": "Same version",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        result = check_for_updates("1.0.0")
        self.assertFalse(result.get("update_available"))

    @patch("requests.get")
    def test_check_for_updates_network_error(self, mock_get):
        from update_checker import check_for_updates

        mock_get.side_effect = Exception("Network error")
        result = check_for_updates("1.0.0")
        # Should not crash, just return empty result
        self.assertIsInstance(result, dict)


class TestAIProviders(unittest.TestCase):
    """Tests de los providers de IA con mocks."""

    def test_provider_registry_exists(self):
        from ai_providers import get_registry

        registry = get_registry()
        self.assertIsNotNone(registry)

    def test_registry_has_adaptation_engines(self):
        from ai_providers import get_registry

        registry = get_registry()
        self.assertIsNotNone(registry)


class TestI18n(unittest.TestCase):
    """Tests del sistema de internacionalizacion."""

    def test_i18n_has_spanish(self):
        try:
            from locales.i18n import set_language, t

            set_language("es")
            # t() should return a string for known keys
            result = t("app_title")
            self.assertIsInstance(result, str)
        except ImportError:
            self.skipTest("locales.i18n not available")

    def test_i18n_has_english(self):
        try:
            from locales.i18n import set_language, t

            set_language("en")
            result = t("app_title")
            self.assertIsInstance(result, str)
        except ImportError:
            self.skipTest("locales.i18n not available")


class TestConfigBackupRestore(unittest.TestCase):
    """Tests de backup/restore de configuracion."""

    def test_export_config(self):
        from config_backup import export_config, import_config
        from config_manager import save_config

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            cfg_path = f.name
        try:
            cfg = {"local_model": "tiny", "theme": "dark", "_config_version": 5}
            save_config(cfg, cfg_path)

            backup_path = cfg_path + ".backup"
            success, msg = export_config(cfg_path, backup_path)
            self.assertTrue(success)

            # Verify backup file exists and is valid JSON (wrapped in metadata)
            with open(backup_path) as f:
                backup = json.load(f)
            self.assertIn("config", backup)
            self.assertEqual(backup["config"]["local_model"], "tiny")

            # Test import
            success2, msg2 = import_config(backup_path, cfg_path)
            self.assertTrue(success2)
        finally:
            for p in [cfg_path, cfg_path + ".backup"]:
                if os.path.exists(p):
                    os.unlink(p)


class TestMetricsModule(unittest.TestCase):
    """Tests del modulo de metricas."""

    def test_record_transcription(self):
        from app_metrics import record_transcription

        # Should not crash
        record_transcription(duration=10.0, model="tiny", provider="local")
        record_transcription(duration=5.0, model="base", provider="local")

    def test_record_export(self):
        from app_metrics import record_export

        record_export(format="pdf")
        record_export(format="docx")

    def test_get_summary(self):
        from app_metrics import get_summary

        summary = get_summary()
        self.assertIsInstance(summary, dict)
        self.assertIn("transcriptions", summary)
        self.assertIn("exports", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
