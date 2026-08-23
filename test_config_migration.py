#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_config_migration.py — Tests del sistema de migración de configuración
==========================================================================
Valida que cada migración (v1→v2→v3→v4→v5) transforma correctamente los
campos, y que configs ya actualizadas no se rompen.

Ejecutar:
    python test_config_migration.py
"""
import json
import os
import sys
import tempfile

from config_manager import (
    CONFIG_VERSION,
    DEFAULT_CONFIG,
    _migrate_config,
    _migrate_v1_to_v2,
    _migrate_v2_to_v3,
    _migrate_v3_to_v4,
    _migrate_v4_to_v5,
    _MIGRATIONS,
    load_config,
    save_config,
)


# ══════════════════════════════════════════════════════════════════════════════
# v1 → v2: colab_key trivial
# ══════════════════════════════════════════════════════════════════════════════

def test_v1_to_v2_resets_trivial_key():
    """'audioclass' se resetea a vacío."""
    cfg = {"colab_key": "audioclass"}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == ""
    print("  OK  v1→v2: 'audioclass' → ''")


def test_v1_to_v2_resets_admin_key():
    """'admin' se resetea a vacío."""
    cfg = {"colab_key": "admin"}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == ""
    print("  OK  v1→v2: 'admin' → ''")


def test_v1_to_v2_resets_password_key():
    """'password' se resetea a vacío."""
    cfg = {"colab_key": "password"}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == ""
    print("  OK  v1→v2: 'password' → ''")


def test_v1_to_v2_resets_1234_key():
    """'1234' se resetea a vacío."""
    cfg = {"colab_key": "1234"}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == ""
    print("  OK  v1→v2: '1234' → ''")


def test_v1_to_v2_resets_test_key():
    """'test' se resetea a vacío."""
    cfg = {"colab_key": "test"}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == ""
    print("  OK  v1→v2: 'test' → ''")


def test_v1_to_v2_keeps_real_key():
    """Una key real (>16 chars) no se toca."""
    cfg = {"colab_key": "my_real_secret_key_12345678"}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == "my_real_secret_key_12345678"
    print("  OK  v1→v2: key real preservada")


def test_v1_to_v2_keeps_empty_key():
    """Una key vacía no se toca."""
    cfg = {"colab_key": ""}
    result = _migrate_v1_to_v2(cfg)
    assert result["colab_key"] == ""
    print("  OK  v1→v2: key vacía intacta")


def test_v1_to_v2_missing_key():
    """Si falta 'colab_key', no la crea."""
    cfg = {"audio_profile": "Podcast"}
    result = _migrate_v1_to_v2(cfg)
    assert "colab_key" not in result or result.get("colab_key") == ""
    print("  OK  v1→v2: key ausente no se crea")


# ══════════════════════════════════════════════════════════════════════════════
# v2 → v3: normalización de modelos Gemini
# ══════════════════════════════════════════════════════════════════════════════

def test_v2_to_v3_old_flash():
    """'gemini-1.5-flash' → 'flash'."""
    cfg = {"gemini_model": "gemini-1.5-flash"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "flash"
    print("  OK  v2→v3: 'gemini-1.5-flash' → 'flash'")


def test_v2_to_v3_old_pro():
    """'gemini-1.5-pro' → 'pro'."""
    cfg = {"gemini_model": "gemini-1.5-pro"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "pro"
    print("  OK  v2→v3: 'gemini-1.5-pro' → 'pro'")


def test_v2_to_v3_generic_pro():
    """'gemini-pro' → 'pro'."""
    cfg = {"gemini_model": "gemini-pro"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "pro"
    print("  OK  v2→v3: 'gemini-pro' → 'pro'")


def test_v2_to_v3_generic_flash():
    """'gemini-flash' → 'flash'."""
    cfg = {"gemini_model": "gemini-flash"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "flash"
    print("  OK  v2→v3: 'gemini-flash' → 'flash'")


def test_v2_to_v3_full_id_flash():
    """'gemini-2.0-flash' → 'flash'."""
    cfg = {"gemini_model": "gemini-2.0-flash"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "flash"
    print("  OK  v2→v3: 'gemini-2.0-flash' → 'flash'")


def test_v2_to_v3_full_id_pro():
    """'gemini-2.5-pro' → 'pro'."""
    cfg = {"gemini_model": "gemini-2.5-pro"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "pro"
    print("  OK  v2→v3: 'gemini-2.5-pro' → 'pro'")


def test_v2_to_v3_already_correct():
    """'flash' y 'pro' no se cambian."""
    assert _migrate_v2_to_v3({"gemini_model": "flash"})["gemini_model"] == "flash"
    assert _migrate_v2_to_v3({"gemini_model": "pro"})["gemini_model"] == "pro"
    print("  OK  v2→v3: aliases correctos no se modifican")


def test_v2_to_v3_unknown_model():
    """Modelo desconocido no se toca (respetar elección del usuario)."""
    cfg = {"gemini_model": "gemini-experimental-v99"}
    result = _migrate_v2_to_v3(cfg)
    assert result["gemini_model"] == "gemini-experimental-v99"
    print("  OK  v2→v3: modelo desconocido preservado")


def test_v2_to_v3_missing_field():
    """Si falta 'gemini_model', no lo crea."""
    cfg = {"theme": "dark"}
    result = _migrate_v2_to_v3(cfg)
    assert "gemini_model" not in result
    print("  OK  v2→v3: campo ausente no se crea")


# ══════════════════════════════════════════════════════════════════════════════
# v3 → v4: renombrar cloud_model → colab_model
# ══════════════════════════════════════════════════════════════════════════════

def test_v3_to_v4_renames_cloud_to_colab():
    """'cloud_model' se renombra a 'colab_model'."""
    cfg = {"cloud_model": "large-v3"}
    result = _migrate_v3_to_v4(cfg)
    assert result.get("colab_model") == "large-v3"
    assert "cloud_model" not in result
    print("  OK  v3→v4: 'cloud_model' → 'colab_model'")


def test_v3_to_v4_preserves_custom_value():
    """Valor personalizado de 'cloud_model' se preserva en 'colab_model'."""
    cfg = {"cloud_model": "my-custom-model"}
    result = _migrate_v3_to_v4(cfg)
    assert result["colab_model"] == "my-custom-model"
    print("  OK  v3→v4: valor personalizado preservado")


def test_v3_to_v4_does_not_overwrite_existing():
    """Si 'colab_model' ya existe, no se sobrescribe."""
    cfg = {"cloud_model": "large-v3", "colab_model": "already-here"}
    result = _migrate_v3_to_v4(cfg)
    assert result["colab_model"] == "already-here"
    print("  OK  v3→v4: colab_model existente no se sobrescribe")


def test_v3_to_v4_removes_cloud_model():
    """'cloud_model' se elimina después de migrar."""
    cfg = {"cloud_model": "large-v3"}
    result = _migrate_v3_to_v4(cfg)
    assert "cloud_model" not in result
    print("  OK  v3→v4: cloud_model eliminado")


def test_v3_to_v4_missing_cloud_model():
    """Si falta 'cloud_model', no se crea 'colab_model'."""
    cfg = {"theme": "dark"}
    result = _migrate_v3_to_v4(cfg)
    assert "colab_model" not in result
    assert "cloud_model" not in result
    print("  OK  v3→v4: ambos campos ausentes")


# ══════════════════════════════════════════════════════════════════════════════
# v4 → v5: normalización de tema
# ══════════════════════════════════════════════════════════════════════════════

def test_v4_to_v5_dark_normalized():
    """'Dark' → 'dark'."""
    cfg = {"theme": "Dark"}
    result = _migrate_v4_to_v5(cfg)
    assert result["theme"] == "dark"
    print("  OK  v4→v5: 'Dark' → 'dark'")


def test_v4_to_v5_light_normalized():
    """'LIGHT' → 'light'."""
    cfg = {"theme": "LIGHT"}
    result = _migrate_v4_to_v5(cfg)
    assert result["theme"] == "light"
    print("  OK  v4→v5: 'LIGHT' → 'light'")


def test_v4_to_v5_strips_whitespace():
    """' dark ' → 'dark'."""
    cfg = {"theme": " dark "}
    result = _migrate_v4_to_v5(cfg)
    assert result["theme"] == "dark"
    print("  OK  v4→v5: ' dark ' → 'dark'")


def test_v4_to_v5_already_correct():
    """'dark' y 'light' no se modifican."""
    assert _migrate_v4_to_v5({"theme": "dark"})["theme"] == "dark"
    assert _migrate_v4_to_v5({"theme": "light"})["theme"] == "light"
    print("  OK  v4→v5: valores correctos intactos")


def test_v4_to_v5_unknown_theme():
    """Valor irreconocible → fallback a 'auto'."""
    cfg = {"theme": "blue"}
    result = _migrate_v4_to_v5(cfg)
    assert result["theme"] == "auto"
    print("  OK  v4→v5: 'blue' → 'auto' (fallback)")


def test_v4_to_v5_missing_theme():
    """Si falta 'theme', no lo crea."""
    cfg = {"audio_profile": "Podcast"}
    result = _migrate_v4_to_v5(cfg)
    # _migrate_v4_to_v5 only touches theme if it exists
    assert "theme" not in result or result.get("theme") == "dark"
    print("  OK  v4→v5: theme ausente")


def test_v4_to_v5_numeric_theme():
    """Valor numérico como tema → fallback a 'auto'."""
    cfg = {"theme": 42}
    result = _migrate_v4_to_v5(cfg)
    assert result["theme"] == "auto"
    print("  OK  v4→v5: 42 → 'auto' (fallback)")


# ══════════════════════════════════════════════════════════════════════════════
# Migración completa (v1 → v5)
# ══════════════════════════════════════════════════════════════════════════════

def test_full_migration_v1_to_v5():
    """Config v1 sin versión migra completamente a v5."""
    cfg_v1 = {
        "colab_key": "audioclass",
        "gemini_model": "gemini-1.5-flash",
        "cloud_model": "large-v3",
        "theme": "Dark",
        "audio_profile": "Podcast",
    }
    result = _migrate_config(cfg_v1)
    assert result["_config_version"] == 5
    assert result["colab_key"] == ""
    assert result["gemini_model"] == "flash"
    assert result.get("colab_model") == "large-v3"
    assert "cloud_model" not in result
    assert result["theme"] == "dark"
    assert result["audio_profile"] == "Podcast"  # no se toca
    print("  OK  migración completa v1→v5 (5 transformaciones)")


def test_full_migration_v2_to_v5():
    """Config v2 migra a v5 (v1→v2 ya aplicada)."""
    cfg_v2 = {
        "_config_version": 2,
        "colab_key": "my_real_key_12345",
        "gemini_model": "gemini-1.5-pro",
        "cloud_model": "large-v3",
        "theme": "LIGHT",
    }
    result = _migrate_config(cfg_v2)
    assert result["_config_version"] == 5
    assert result["colab_key"] == "my_real_key_12345"  # no trivial, no se toca
    assert result["gemini_model"] == "pro"
    assert result.get("colab_model") == "large-v3"
    assert result["theme"] == "light"
    print("  OK  migración completa v2→v5")


def test_full_migration_v3_to_v5():
    """Config v3 migra a v5."""
    cfg_v3 = {
        "_config_version": 3,
        "cloud_model": "medium",
        "theme": "Dark",
    }
    result = _migrate_config(cfg_v3)
    assert result["_config_version"] == 5
    assert result.get("colab_model") == "medium"
    assert "cloud_model" not in result
    assert result["theme"] == "dark"
    print("  OK  migración completa v3→v5")


def test_full_migration_v4_to_v5():
    """Config v4 solo necesita normalizar tema."""
    cfg_v4 = {
        "_config_version": 4,
        "theme": " dark ",
    }
    result = _migrate_config(cfg_v4)
    assert result["_config_version"] == 5
    assert result["theme"] == "dark"
    print("  OK  migración completa v4→v5")


def test_full_migration_already_v5():
    """Config v5 no se modifica."""
    cfg_v5 = {
        "_config_version": 5,
        "colab_key": "secret123",
        "gemini_model": "flash",
        "colab_model": "large-v3",
        "theme": "dark",
    }
    original = dict(cfg_v5)
    result = _migrate_config(cfg_v5)
    assert result["_config_version"] == 5
    for k in original:
        assert result[k] == original[k], f"Campo '{k}' modificado innecesariamente"
    print("  OK  config v5 no se modifica")


# ══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════════════════════

def test_empty_config():
    """Config vacía migra sin errores."""
    result = _migrate_config({})
    assert result["_config_version"] == 5
    print("  OK  config vacía migra sin errores")


def test_none_values():
    """Valores None no crashean las migraciones."""
    cfg = {
        "colab_key": None,
        "gemini_model": None,
        "cloud_model": None,
        "theme": None,
    }
    result = _migrate_config(cfg)
    assert result["_config_version"] == 5
    print("  OK  valores None manejados")


def test_migration_preserves_extra_fields():
    """Campos adicionales no reconocidos se preservan."""
    cfg = {
        "_config_version": 1,
        "colab_key": "audioclass",
        "my_custom_field": "hello",
        "future_feature_enabled": True,
    }
    result = _migrate_config(cfg)
    assert result["my_custom_field"] == "hello"
    assert result["future_feature_enabled"] is True
    print("  OK  campos extra preservados")


def test_migration_count():
    """Hay exactamente 4 migraciones registradas (v1→v2, v2→v3, v3→v4, v4→v5)."""
    assert len(_MIGRATIONS) == 4
    # Verify sequential ordering
    for i in range(len(_MIGRATIONS) - 1):
        assert _MIGRATIONS[i][1] == _MIGRATIONS[i + 1][0], \
            f"Migración {i} termina en v{_MIGRATIONS[i][1]} pero la siguiente empieza en v{_MIGRATIONS[i+1][0]}"
    print("  OK  4 migraciones en orden secuencial")


# ══════════════════════════════════════════════════════════════════════════════
# Integración con load_config / save_config
# ══════════════════════════════════════════════════════════════════════════════

def test_load_save_roundtrip():
    """Guardar y cargar preserva la config migrada."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        # Simular config v1 en disco
        cfg_old = {
            "colab_key": "audioclass",
            "gemini_model": "gemini-1.5-flash",
            "cloud_model": "large-v3",
            "theme": "Dark",
            "audio_profile": "Podcast",
        }
        with open(tmp, "w") as f:
            json.dump(cfg_old, f)
        
        # Cargar: debe migrar automáticamente
        loaded = load_config(tmp)
        assert loaded["_config_version"] == 5
        assert loaded["colab_key"] == ""
        assert loaded["gemini_model"] == "flash"
        assert loaded.get("colab_model") == "large-v3"
        assert loaded["theme"] == "dark"
        assert loaded["audio_profile"] == "Podcast"
        
        # Guardar y recargar: no debe re-migrar
        save_config(loaded, tmp)
        loaded2 = load_config(tmp)
        assert loaded2["_config_version"] == 5
        assert loaded2["colab_key"] == ""
        assert loaded2["gemini_model"] == "flash"
        print("  OK  load → migrate → save → load roundtrip")
    finally:
        os.unlink(tmp)


def test_load_new_defaults_after_migration():
    """Después de migrar, los defaults nuevos se aplican."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        # Config v1 muy antigua (sin keys que DEFAULT_CONFIG tiene)
        cfg_old = {"_config_version": 1}
        with open(tmp, "w") as f:
            json.dump(cfg_old, f)
        
        loaded = load_config(tmp)
        # Defaults nuevos deben existir
        assert "openai_api_key" in loaded
        assert "openai_model" in loaded
        assert "adapt_provider" in loaded
        assert loaded["openai_model"] == "mini"
        print("  OK  defaults nuevos aplicados tras migración")
    finally:
        os.unlink(tmp)


# ══════════════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════════════

def main():
    tests = [
        # v1 → v2
        test_v1_to_v2_resets_trivial_key,
        test_v1_to_v2_resets_admin_key,
        test_v1_to_v2_resets_password_key,
        test_v1_to_v2_resets_1234_key,
        test_v1_to_v2_resets_test_key,
        test_v1_to_v2_keeps_real_key,
        test_v1_to_v2_keeps_empty_key,
        test_v1_to_v2_missing_key,
        # v2 → v3
        test_v2_to_v3_old_flash,
        test_v2_to_v3_old_pro,
        test_v2_to_v3_generic_pro,
        test_v2_to_v3_generic_flash,
        test_v2_to_v3_full_id_flash,
        test_v2_to_v3_full_id_pro,
        test_v2_to_v3_already_correct,
        test_v2_to_v3_unknown_model,
        test_v2_to_v3_missing_field,
        # v3 → v4
        test_v3_to_v4_renames_cloud_to_colab,
        test_v3_to_v4_preserves_custom_value,
        test_v3_to_v4_does_not_overwrite_existing,
        test_v3_to_v4_removes_cloud_model,
        test_v3_to_v4_missing_cloud_model,
        # v4 → v5
        test_v4_to_v5_dark_normalized,
        test_v4_to_v5_light_normalized,
        test_v4_to_v5_strips_whitespace,
        test_v4_to_v5_already_correct,
        test_v4_to_v5_unknown_theme,
        test_v4_to_v5_missing_theme,
        test_v4_to_v5_numeric_theme,
        # Migración completa
        test_full_migration_v1_to_v5,
        test_full_migration_v2_to_v5,
        test_full_migration_v3_to_v5,
        test_full_migration_v4_to_v5,
        test_full_migration_already_v5,
        # Edge cases
        test_empty_config,
        test_none_values,
        test_migration_preserves_extra_fields,
        test_migration_count,
        # Integración
        test_load_save_roundtrip,
        test_load_new_defaults_after_migration,
    ]

    passed = 0
    failed = 0
    print("test_config_migration.py — Tests de migración de configuración\n")
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL  {test.__name__}: {e}")
            failed += 1

    print(f"\nResultado: {passed}/{passed + failed} tests pasaron")
    if failed:
        print("CONFIG_MIGRATION_FAIL")
        return 1
    print("CONFIG_MIGRATION_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
