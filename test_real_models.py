#!/usr/bin/env python3
"""
test_real_models.py — Tests con modelos Whisper reales y audio real.

Requiere: models/tiny.pt y prueba_voz_es.wav en el directorio del proyecto.
"""

import os
import time
import unittest


class TestRealModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from audioclass_core import LocalWhisperEngine

        cls.engine = LocalWhisperEngine("tiny", "es")
        cls.engine.load()
        # Esperar a que el modelo cargue (carga en hilo background)
        for _ in range(50):
            if cls.engine.ready:
                break
            time.sleep(0.1)
        assert cls.engine.ready, "Modelo no cargó tras 5s"
        assert os.path.exists("prueba_voz_es.wav"), "Falta prueba_voz_es.wav"

    def test_transcribe_real_audio(self):
        """Transcripcion de audio real en español."""
        start = time.time()
        result = self.engine.transcribe("prueba_voz_es.wav")
        elapsed = time.time() - start

        # Validaciones basicas
        self.assertEqual(result.get("language"), "es")
        self.assertGreater(len(result.get("text", "")), 50)
        self.assertLess(elapsed, 30)

        print(f"  Texto: {result.get('text', '')[:100]}...")
        print(f"  Tiempo: {elapsed:.2f}s")

    def test_vad_deterministic(self):
        """process(vad=True) deterministico con seed fija."""
        import numpy as np

        from audioclass_core import AudioPipeline

        np.random.seed(42)
        pipe = AudioPipeline("Clase Universitaria")
        sr = 44100
        t = np.linspace(0, 1.0, sr, dtype=np.float64)
        audio = np.zeros(sr, dtype=np.float64)
        audio[22050:] = 0.5 * np.sin(2 * np.pi * 440 * t[22050:])
        result1 = pipe.process(audio, vad=True)
        result2 = pipe.process(audio, vad=True)
        assert np.allclose(result1, result2), "VAD no deterministico"
        assert len(result1) == len(result2)


if __name__ == "__main__":
    import unittest

    unittest.main()
