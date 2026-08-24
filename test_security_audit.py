"""test_security_audit.py — Auditoria de seguridad automatizada.

Verifica:
- Path traversal protection en exportaciones
- Ausencia de hardcoded credentials en produccion
- Validacion de inputs criticos
- Integridad de configuracion
"""

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))


class TestPathTraversalProtection(unittest.TestCase):
    """Verifica que todas las rutas de exportacion estan protegidas."""

    def test_validate_export_path_blocks_dotdot(self):
        from export_utils import validate_export_path

        attacks = [
            "/tmp/export/../../etc/passwd",
            "../etc/shadow",
            "/tmp/test/../../../etc/hostname",
        ]
        for attack in attacks:
            with self.assertRaises(ValueError, msg=f"Should block: {attack}"):
                validate_export_path(attack)

    def test_validate_export_path_blocks_tilde(self):
        from export_utils import validate_export_path

        with self.assertRaises(ValueError):
            validate_export_path("~/../../etc/passwd")

    def test_validate_export_path_blocks_absolute_escape(self):
        from export_utils import validate_export_path

        tmp = tempfile.gettempdir()
        with self.assertRaises(ValueError):
            validate_export_path("/etc/passwd", allowed_dir=tmp)

    def test_validate_export_path_accepts_valid(self):
        from export_utils import validate_export_path

        tmp = tempfile.gettempdir()
        valid_paths = [
            os.path.join(tmp, "test.pdf"),
            os.path.join(tmp, "subdir", "test.docx"),
            os.path.join(tmp, "test_file_2024.pdf"),
        ]
        for path in valid_paths:
            result = validate_export_path(path, allowed_dir=tmp)
            self.assertTrue(result, f"Should accept: {path}")

    def test_validate_empty_path(self):
        from export_utils import validate_export_path

        with self.assertRaises(ValueError):
            validate_export_path("")

    def test_validate_none_path(self):
        from export_utils import validate_export_path

        with self.assertRaises((ValueError, TypeError)):
            validate_export_path(None)


class TestNoHardcodedCredentials(unittest.TestCase):
    """Verifica que no hay credenciales hardcodeadas en archivos de produccion."""

    PROD_FILES = [
        "audioclass_v91.py",
        "audioclass_core.py",
        "config_manager.py",
        "ai_providers.py",
        "recording_engine.py",
        "export_utils.py",
        "app_metrics.py",
        "config_backup.py",
    ]

    def test_no_hardcoded_api_keys(self):
        """Busca patrones de API keys reales en archivos de produccion."""
        patterns = [
            r"AIza[A-Za-z0-9_-]{35}",  # Google API key
            r"sk-[A-Za-z0-9]{32,}",  # OpenAI key
            r"ghp_[A-Za-z0-9]{36}",  # GitHub PAT
            r"glpat-[A-Za-z0-9_-]{20,}",  # GitLab PAT
            r"AKIA[0-9A-Z]{16}",  # AWS Access Key
        ]
        for fname in self.PROD_FILES:
            if not os.path.exists(fname):
                continue
            with open(fname, encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for pattern in patterns:
                matches = re.findall(pattern, content)
                self.assertEqual(len(matches), 0, f"Hardcoded credential found in {fname}: {matches}")

    def test_no_hardcoded_passwords(self):
        """Busca passwords hardcodeadas en archivos de produccion."""
        password_patterns = [
            r'password\s*=\s*["\'][^"\']{8,}["\']',
            r'passwd\s*=\s*["\'][^"\']{8,}["\']',
            r'secret\s*=\s*["\'][^"\']{16,}["\']',
        ]
        skip_files = set()
        for fname in self.PROD_FILES:
            if not os.path.exists(fname) or fname in skip_files:
                continue
            with open(fname, encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    # Skip comments and test data
                    stripped = line.strip()
                    if stripped.startswith("#") or "test" in fname.lower():
                        continue
                    for pattern in password_patterns:
                        matches = re.findall(pattern, line, re.IGNORECASE)
                        if matches:
                            self.fail(f"Possible hardcoded password in {fname}:{line_num}: {matches[0][:30]}...")


class TestConfigIntegrity(unittest.TestCase):
    """Verifica la integridad del sistema de configuracion."""

    def test_default_config_has_required_keys(self):
        from config_manager import DEFAULT_CONFIG

        required = [
            "local_model",
            "theme",
            "language",
            "adapt_provider",
        ]
        for key in required:
            self.assertIn(key, DEFAULT_CONFIG, f"Missing required config key: {key}")

    def test_config_version_set_on_load(self):
        import tempfile

        from config_manager import load_config

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            import json

            json.dump({"local_model": "tiny"}, f)
            path = f.name
        try:
            loaded = load_config(path)
            version = loaded.get("_config_version", 0)
            self.assertGreaterEqual(version, 1, "Config version should be set on load")
        finally:
            import os

            os.unlink(path)

    def test_load_save_integrity(self):
        from config_manager import load_config, save_config

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            path = f.name
        try:
            original = {
                "local_model": "test_model",
                "theme": "dark",
                "language": "es",
                "_config_version": 99,
                "adapt_provider": "gemini",
                "gemini_api_key": "test-key-12345",
            }
            save_config(original, path)
            loaded = load_config(path)

            # Core fields should survive roundtrip
            self.assertEqual(loaded["local_model"], "test_model")
            self.assertEqual(loaded["theme"], "dark")
            self.assertEqual(loaded["language"], "es")
        finally:
            os.unlink(path)


class TestExportPathConsistency(unittest.TestCase):
    """Verifica que todas las funciones de export usan validate_export_path."""

    def test_export_utils_has_validation(self):
        with open("export_utils.py") as f:
            content = f.read()
        self.assertIn("validate_export_path", content)
        self.assertIn("safe_export_path", content)

    def test_main_app_imports_validation(self):
        with open("audioclass_v91.py") as f:
            content = f.read()
        self.assertIn("validate_export_path", content)


class TestMetricsModule(unittest.TestCase):
    """Verifica el modulo de metricas."""

    def test_metrics_not_empty(self):
        with open("app_metrics.py") as f:
            content = f.read()
        self.assertGreater(len(content), 500)

    def test_metrics_has_prometheus(self):
        with open("app_metrics.py") as f:
            content = f.read()
        self.assertIn("to_prometheus_text", content)

    def test_metrics_persistence(self):
        from app_metrics import get_summary

        summary = get_summary()
        self.assertIn("transcriptions", summary)
        self.assertIn("exports", summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
