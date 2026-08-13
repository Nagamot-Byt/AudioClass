# -*- coding: utf-8 -*-
"""Pruebas offline de los motores de adaptacion (Gemini + OpenAI).

No toca la red: valida el contrato comun (test_key/adapt), la resolucion de
modelos, la fabrica y los mensajes de error sin API key.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audioclass_core import (GeminiAdaptationEngine, OpenAIAdaptationEngine,
                             build_adaptation_engine)


def test_contrato_comun():
    g = GeminiAdaptationEngine("", "flash")
    o = OpenAIAdaptationEngine("", "mini")
    # Ambos exponen los mismos TEMPLATES, test_key y adapt
    assert g.TEMPLATES and set(g.TEMPLATES) == set(o.TEMPLATES)
    assert callable(g.test_key) and callable(g.adapt)
    assert callable(o.test_key) and callable(o.adapt)
    # Nombre del proveedor distinto
    assert g.PROVIDER == "Gemini" and o.PROVIDER == "OpenAI"


def test_modelos():
    assert GeminiAdaptationEngine("", "flash")._model_name() == "gemini-2.0-flash"
    assert GeminiAdaptationEngine("", "pro")._model_name() == "gemini-2.5-pro"
    assert GeminiAdaptationEngine("", "xx")._model_name() == "gemini-2.0-flash"
    assert OpenAIAdaptationEngine("", "mini")._model_name() == "gpt-4o-mini"
    assert OpenAIAdaptationEngine("", "gpt4o")._model_name() == "gpt-4o"
    assert OpenAIAdaptationEngine("", "xx")._model_name() == "gpt-4o-mini"


def test_sin_api_key():
    ok, msg = GeminiAdaptationEngine("", "flash").test_key()
    assert not ok and "no configurada" in msg.lower()
    ok, msg = OpenAIAdaptationEngine("", "mini").test_key()
    assert not ok and "no configurada" in msg.lower()
    # Key corta tambien rechazada sin tocar la red
    ok, _ = OpenAIAdaptationEngine("abc", "mini").test_key()
    assert not ok
    ok, _ = GeminiAdaptationEngine("abc", "flash").test_key()
    assert not ok


def test_adapt_template_invalido():
    # Template inexistente -> error sin llamar a la red
    res = OpenAIAdaptationEngine("sk-test-123456", "mini").adapt("hola", "No Existe")
    assert "error" in res and "no existe" in res["error"]
    res = GeminiAdaptationEngine("AIza-test-123456", "flash").adapt("hola", "No Existe")
    assert "error" in res and "no existe" in res["error"]


def test_fabrica():
    e = build_adaptation_engine("gemini", gemini_api_key="k", gemini_model="flash")
    assert isinstance(e, GeminiAdaptationEngine)
    e = build_adaptation_engine("openai", openai_api_key="k", openai_model="mini")
    assert isinstance(e, OpenAIAdaptationEngine)
    e = build_adaptation_engine()  # default: gemini
    assert isinstance(e, GeminiAdaptationEngine)
    e = build_adaptation_engine("desconocido")  # fallback: gemini
    assert isinstance(e, GeminiAdaptationEngine)


def main():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"ADAPT_ENGINES_ALL_OK ({len(fns)} tests)")


if __name__ == "__main__":
    main()
