#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_config_manager.py — Tests unitarios para config_manager.py
================================================================
Valida: defaults, carga/guardado, cifrado/descifrado de secretos,
        integridad de campos secretos, backward compat.
"""
import os
import sys
import json
import tempfile
import pytest

# Asegurar que el directorio del proyecto esta en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import (
    DEFAULT_CONFIG,
    _SECRET_FIELDS,
    _encrypt_secret,
    _decrypt_secret,
    load_config,
    save_config,
)


class TestDefaults:
    """Verifica que DEFAULT_CONFIG tiene todas las claves esperadas."""

    def test_has_required_keys(self):
        required = [
            "gemini_api_key", "colab_url", "colab_key",
            "transcription_mode", "local_model", "whisper_language",
            "adapt_provider", "openai_api_key", "openai_model",
            "theme", "mic_device", "first_run",
            "ia_consent", "rec_consent_ack",
        ]
        for k in required:
            assert k in DEFAULT_CONFIG, f"Missing key: {k}"

    def test_secret_fields_defined(self):
        assert len(_SECRET_FIELDS) > 0
        for f in _SECRET_FIELDS:
            assert f in DEFAULT_CONFIG, f"Secret field {f} not in DEFAULT_CONFIG"

    def test_no_emoji_in_defaults(self):
        """Los defaults no deben contener emojis (regla del proyecto)."""
        for k, v in DEFAULT_CONFIG.items():
            if isinstance(v, str):
                # Check for common emoji ranges
                for c in v:
                    cp = ord(c)
                    assert not (0x1F600 <= cp <= 0x1F64F or 0x1F300 <= cp <= 0x1F5FF or
                               0x1F680 <= cp <= 0x1F6FF or 0x1F1E0 <= cp <= 0x1F1FF), \
                        f"Emoji found in DEFAULT_CONFIG['{k}']"


class TestEncryptDecrypt:
    """Verifica el ciclo de cifrado/descifrado de secretos."""

    def test_roundtrip_base64(self):
        """Un valor cifrado debe descifrarse al original."""
        original = "my_secret_api_key_12345"
        encrypted = _encrypt_secret(original)
        assert encrypted != original
        decrypted = _decrypt_secret(encrypted)
        assert decrypted == original

    def test_empty_string(self):
        """Cifrar string vacio devuelve vacio."""
        assert _encrypt_secret("") == ""
        assert _decrypt_secret("") == ""

    def test_none_handling(self):
        """None se trata como string vacio."""
        assert _encrypt_secret(None) == ""
        assert _decrypt_secret(None) == ""

    def test_prefix(self):
        """El cifrado debe usar prefijo 'b64:' o 'dpapi:'."""
        encrypted = _encrypt_secret("test_value")
        assert encrypted.startswith("b64:") or encrypted.startswith("dpapi:")

    def test_legacy_plaintext_passthrough(self):
        """Valores en texto plano sin prefijo se devuelven tal cual."""
        assert _decrypt_secret("plain_text_key") == "plain_text_key"

    def test_unicode_secret(self):
        """Secretos con caracteres unicode se manejan correctamente."""
        original = "clave_con_tildes_y_ñ"
        encrypted = _encrypt_secret(original)
        decrypted = _decrypt_secret(encrypted)
        assert decrypted == original


class TestLoadSaveConfig:
    """Verifica carga y guardado de configuracion en archivos temporales."""

    def test_save_and_load(self, tmp_path):
        """Guardar y cargar una config debe preservar todos los valores."""
        cfg_path = str(tmp_path / "test_config.json")
        cfg = DEFAULT_CONFIG.copy()
        cfg["local_model"] = "small"
        cfg["theme"] = "light"
        cfg["gemini_api_key"] = "test_key_12345"

        save_config(cfg, path=cfg_path)
        loaded = load_config(path=cfg_path)

        assert loaded["local_model"] == "small"
        assert loaded["theme"] == "light"
        # API key se cifra al guardar y se descifra al cargar
        assert loaded["gemini_api_key"] == "test_key_12345"

    def test_load_missing_file_returns_defaults(self, tmp_path):
        """Si el archivo no existe, devuelve DEFAULT_CONFIG."""
        cfg_path = str(tmp_path / "nonexistent.json")
        loaded = load_config(path=cfg_path)
        assert loaded == DEFAULT_CONFIG

    def test_load_corrupt_file_returns_defaults(self, tmp_path):
        """Si el JSON esta corrupto, devuelve DEFAULT_CONFIG."""
        cfg_path = str(tmp_path / "corrupt.json")
        with open(cfg_path, "w") as f:
            f.write("{invalid json!!!")

        loaded = load_config(path=cfg_path)
        assert loaded == DEFAULT_CONFIG

    def test_defaults_added_on_load(self, tmp_path):
        """Claves faltantes se rellenan con defaults al cargar."""
        cfg_path = str(tmp_path / "partial.json")
        with open(cfg_path, "w") as f:
            json.dump({"local_model": "tiny"}, f)

        loaded = load_config(path=cfg_path)
        assert loaded["local_model"] == "tiny"
        # Clave faltante se rellena
        assert loaded["theme"] == DEFAULT_CONFIG["theme"]
        assert loaded["first_run"] == DEFAULT_CONFIG["first_run"]

    def test_secrets_encrypted_on_disk(self, tmp_path):
        """Los secretos se guardan cifrados (no en texto plano) en disco."""
        cfg_path = str(tmp_path / "secrets.json")
        cfg = DEFAULT_CONFIG.copy()
        cfg["gemini_api_key"] = "super_secret"

        save_config(cfg, path=cfg_path)

        with open(cfg_path, "r") as f:
            raw = json.load(f)

        # En disco debe estar cifrado, no en texto plano
        assert raw["gemini_api_key"] != "super_secret"
        assert raw["gemini_api_key"].startswith("b64:") or \
               raw["gemini_api_key"].startswith("dpapi:")

    def test_backward_compat_with_legacy_config(self, tmp_path):
        """Configurations antiguas sin campos nuevos se actualizan con defaults."""
        cfg_path = str(tmp_path / "old_config.json")
        # Simular una config vieja sin los campos nuevos
        old_cfg = {
            "gemini_api_key": "",
            "colab_url": "",
            "local_model": "tiny",
        }
        with open(cfg_path, "w") as f:
            json.dump(old_cfg, f)

        loaded = load_config(path=cfg_path)
        # Campo viejo se preserva
        assert loaded["local_model"] == "tiny"
        # Campos nuevos se agregan con defaults
        assert "adapt_provider" in loaded
        assert "openai_api_key" in loaded
        assert "ia_consent" in loaded
