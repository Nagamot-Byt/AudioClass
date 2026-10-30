"""test_model_manager.py — Tests unitarios e integrados para ModelManager y Ciclo de Vida de Modelos.

Valida:
  1. Resolución de rutas e inspección de modelos (Whisper, CT2, Parakeet).
  2. Cálculo y verificación de hashes SHA-256.
  3. Soporte de reanudación de descargas (Range) y cancelación cooperativa.
  4. Descarga por inactividad y liberación de memoria RAM/VRAM (unload).
  5. Auto-reactivación transparente de modelos tras el reposo.
  6. Resumen de almacenamiento y limpieza de temporales.

Patrón de éxito: MODEL_MANAGER_OK
"""

import hashlib
import io
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from audioclass_core import LocalWhisperEngine, SherpaParakeetEngine
from services.model_manager import MODEL_REGISTRY, ModelManager, get_default_model_manager
from services.transcription_service import TranscriptionService


class TestModelManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="audioclass_test_model_mgr_")
        self.mgr = ModelManager(base_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_singleton_and_instance(self):
        inst1 = get_default_model_manager()
        inst2 = ModelManager.get_instance()
        self.assertIs(inst1, inst2)
        self.assertIsNotNone(self.mgr.base_dir)

    def test_model_registry_entries(self):
        self.assertIn("whisper-tiny", MODEL_REGISTRY)
        self.assertIn("whisper-base", MODEL_REGISTRY)
        self.assertIn("parakeet-tdt-0.6b-v3", MODEL_REGISTRY)
        self.assertEqual(MODEL_REGISTRY["whisper-tiny"].size_mb, 75.0)

    def test_sha256_calculation_and_verification(self):
        test_file = os.path.join(self.temp_dir, "test_file.bin")
        content = b"AudioClass v9.1 Test Data for SHA-256 Integrity Verification"
        with open(test_file, "wb") as f:
            f.write(content)

        expected_hash = hashlib.sha256(content).hexdigest()
        calc_hash = self.mgr.calculate_sha256(test_file)
        self.assertEqual(calc_hash, expected_hash)
        self.assertTrue(self.mgr.verify_checksum(test_file, expected_hash))
        self.assertFalse(self.mgr.verify_checksum(test_file, "0" * 64))

    def test_resolve_model_path_not_found(self):
        # En temp_dir vacío no debe encontrar nada
        path = self.mgr.resolve_model_path("whisper", "non_existent_model_xyz")
        self.assertIsNone(path)
        self.assertFalse(self.mgr.is_model_available("whisper", "non_existent_model_xyz"))

    def test_resolve_and_detect_parakeet(self):
        parakeet_dir = os.path.join(self.temp_dir, "models_parakeet", "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8")
        os.makedirs(parakeet_dir, exist_ok=True)
        for fname in ["encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"]:
            with open(os.path.join(parakeet_dir, fname), "wb") as f:
                f.write(b"dummy_onnx_bytes")

        resolved = self.mgr.resolve_model_path("parakeet", "parakeet-tdt-0.6b-v3")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved, parakeet_dir)
        self.assertTrue(self.mgr.is_model_available("parakeet", "parakeet-tdt-0.6b-v3"))

    def test_download_resumable_fresh_and_completed(self):
        dest_path = os.path.join(self.temp_dir, "download_test.bin")
        data = b"ABCDEFGHIJ" * 1000
        data_hash = hashlib.sha256(data).hexdigest()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Length": str(len(data))}
        mock_resp.read.side_effect = [data[:5000], data[5000:], b""]
        mock_resp.__enter__.return_value = mock_resp

        progress_calls = []

        def _cb(dl, tot, pct, speed):
            progress_calls.append((dl, tot, pct))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = self.mgr.download_with_resume(
                url="http://fakeurl/model.bin",
                dest_path=dest_path,
                expected_sha256=data_hash,
                progress_callback=_cb,
            )

        self.assertEqual(res, dest_path)
        self.assertTrue(os.path.isfile(dest_path))
        with open(dest_path, "rb") as f:
            self.assertEqual(f.read(), data)
        self.assertTrue(len(progress_calls) > 0)
        self.assertEqual(progress_calls[-1][2], 100.0)

    def test_download_resumable_with_existing_part(self):
        dest_path = os.path.join(self.temp_dir, "resume_test.bin")
        part_path = dest_path + ".part"
        data = b"1234567890" * 1000
        initial_part = data[:3000]
        remaining = data[3000:]
        data_hash = hashlib.sha256(data).hexdigest()

        with open(part_path, "wb") as f:
            f.write(initial_part)

        mock_resp = MagicMock()
        mock_resp.status = 206
        mock_resp.headers = {"Content-Length": str(len(remaining))}
        mock_resp.read.side_effect = [remaining, b""]
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = self.mgr.download_with_resume(
                url="http://fakeurl/resume.bin",
                dest_path=dest_path,
                expected_sha256=data_hash,
            )

        self.assertEqual(res, dest_path)
        self.assertFalse(os.path.exists(part_path))
        with open(dest_path, "rb") as f:
            self.assertEqual(f.read(), data)

    def test_download_cancellation(self):
        dest_path = os.path.join(self.temp_dir, "cancel_test.bin")
        cancel_ev = threading.Event()
        cancel_ev.set()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Length": "1000"}
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(InterruptedError):
                self.mgr.download_with_resume(
                    url="http://fakeurl/cancel.bin",
                    dest_path=dest_path,
                    cancel_event=cancel_ev,
                )

    def test_download_corrupt_hash_raises_and_cleans_part(self):
        dest_path = os.path.join(self.temp_dir, "corrupt_test.bin")
        part_path = dest_path + ".part"
        bad_data = b"corrupted payload"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {"Content-Length": str(len(bad_data))}
        mock_resp.read.side_effect = [bad_data, b""]
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(ValueError):
                self.mgr.download_with_resume(
                    url="http://fakeurl/bad.bin",
                    dest_path=dest_path,
                    expected_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                )
        self.assertFalse(os.path.exists(dest_path))
        self.assertFalse(os.path.exists(part_path))

    def test_storage_summary_and_clean_cache(self):
        models_dir = os.path.join(self.temp_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        with open(os.path.join(models_dir, "junk.part"), "wb") as f:
            f.write(b"x" * 1024)

        summary = self.mgr.get_storage_summary()
        self.assertIn("models_dir_mb", summary)
        self.assertIn("total_mb", summary)

        freed = self.mgr.clean_cache()
        self.assertEqual(freed, 1024)
        self.assertFalse(os.path.exists(os.path.join(models_dir, "junk.part")))


class TestModelLifecycleAndMemory(unittest.TestCase):
    def test_local_whisper_engine_unload(self):
        engine = LocalWhisperEngine(model_name="tiny")
        engine.model = MagicMock()
        engine.ready = True
        engine._model_cache["tiny"] = [MagicMock()]
        engine._model_template["tiny"] = MagicMock()

        self.assertIsNotNone(engine.model)
        self.assertTrue(engine.ready)

        engine.unload()

        self.assertIsNone(engine.model)
        self.assertFalse(engine.ready)
        self.assertEqual(len(engine._model_cache), 0)
        self.assertEqual(len(engine._model_template), 0)
        self.assertTrue(engine.unloaded_idle)

    def test_sherpa_parakeet_engine_unload(self):
        engine = SherpaParakeetEngine()
        engine.recognizer = MagicMock()
        engine.ready = True

        self.assertIsNotNone(engine.recognizer)
        self.assertTrue(engine.ready)

        engine.unload()

        self.assertIsNone(engine.recognizer)
        self.assertFalse(engine.ready)
        self.assertTrue(engine.unloaded_idle)

    def test_transcription_service_idle_unload(self):
        svc = TranscriptionService(config={"idle_unload_timeout": 1.0})
        svc.local_engine = MagicMock()
        svc.local_engine.ready = True
        svc.last_activity = time.time() - 2.0  # Inactivo hace 2s (umbral 1.0s)

        unloaded = svc.check_idle_unload()
        self.assertTrue(unloaded)
        svc.local_engine.unload.assert_called_once()

    def test_transcription_service_no_unload_when_active(self):
        svc = TranscriptionService(config={"idle_unload_timeout": 10.0})
        svc.local_engine = MagicMock()
        svc.local_engine.ready = True
        svc.last_activity = time.time()  # Recién activo

        unloaded = svc.check_idle_unload()
        self.assertFalse(unloaded)
        svc.local_engine.unload.assert_not_called()

    def test_transcription_service_no_unload_during_transcribe(self):
        svc = TranscriptionService(config={"idle_unload_timeout": 0.1})
        svc.local_engine = MagicMock()
        svc.local_engine.ready = True
        svc.last_activity = time.time() - 5.0
        svc._is_transcribing = True

        unloaded = svc.check_idle_unload()
        self.assertFalse(unloaded)
        svc.local_engine.unload.assert_not_called()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if result.wasSuccessful():
        print("\nMODEL_MANAGER_OK")
        sys.exit(0)
    else:
        print("\nMODEL_MANAGER_FAIL")
        sys.exit(1)
