# -*- coding: utf-8 -*-
"""recording_engine.py — Mixin de grabacion de audio para AudioClass.

Modulo extraido de audioclass_v91.py. Contiene la logica de grabacion
(buffer circular, streaming a disco, flusher, loop de captura) como
clase mixin que App hereda.

El mixin asume que la clase que lo hereda tiene estos atributos:
    - self.config: dict de configuracion
    - self.recording: bool de estado
    - self.stop_ev: threading.Event
    - self.buffer: list de arrays numpy
    - self.q: queue.Queue para mensajes UI
    - self._msg(tipo, titulo, texto): metodo de mensajes
    - self._set_step(n): metodo de progreso

El mixin NO depende de customtkinter ni de la GUI.

Uso:
    class App(RecordingMixin, ...):
        pass
"""
import os
import tempfile
import threading
import time

import numpy as np
import sounddevice as sd


# ── Constantes de audio ───────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "float32"
CHUNK_SIZE = 4096
VISUAL_SAMPLES = 8000  # ~0.5s a 16kHz


def mic_device_id_for(config):
    """Resuelve el ID del dispositivo de microfono desde la config.

    Args:
        config: Dict de configuracion (puede tener 'mic_device').

    Returns:
        int o None: ID del dispositivo para sounddevice.
    """
    dev = config.get("mic_device") if config else None
    if dev and isinstance(dev, (int, str)):
        try:
            return int(dev)
        except (ValueError, TypeError):
            pass
    return None


class RecordingMixin:
    """Mixin que proporciona logica de grabacion de audio.

    Metodos principales:
        begin_recording(): Inicia la grabacion (con consentimiento).
        stoprec(): Detiene la grabacion y lanza procesamiento.
        recloop(): Loop de captura de audio (PortAudio callback).
        rec_flusher(): Vuelca buffer a disco por tramos.
    """

    def begin_recording(self):
        """Arranca la grabacion real (invocada por mic_probe_done).

        Contiene el cuerpo original de _startrec a partir de
        self.recording = True. Maneja consentimiento, streaming a
        disco y actualizacion de UI.
        """
        # Consentimiento obligatorio
        if not self.config.get("rec_consent_ack", False):
            if not self._prompt_rec_consent():
                try:
                    self.lstatus.configure(text="Listo")
                except Exception:
                    pass
                return
            self.config["rec_consent_ack"] = True
            from config_manager import save_config
            save_config(self.config)

        self.recording = True
        self.stop_ev.clear()
        self._stop_done = False
        self.buffer = []
        self._audio_overflows = 0
        self.vu_clips = 0
        self.vu_low = 0
        self.vu_rms_hist = []
        self.vu_static = False
        self.vu_rms_hist_full = []

        # Streaming a disco: archivo temporal .raw (float32)
        try:
            self._rec_raw_path = os.path.join(
                tempfile.gettempdir(),
                f"ac_rec_{int(time.time() * 1000)}.raw"
            )
            self._rec_fp = open(self._rec_raw_path, "wb")
        except Exception as e:
            self.recording = False
            self._msg("error", "Grabacion", f"No se pudo iniciar: {str(e)[:60]}")
            return

        self._rec_bytes = 0
        self._flusher_thread = None

        # Resetear VU meter
        try:
            self.vu_bar.set(0)
            self.vu_lbl.configure(text="-inf dB")
        except Exception:
            pass
        try:
            self.vu_warn.configure(text="")
            if hasattr(self, "vu_hist"):
                self.vu_hist.delete("all")
        except Exception:
            pass

        self.vizbuf = np.zeros(VISUAL_SAMPLES, dtype=np.float32)
        self.cancel = False
        self._set_step(1)

        # UI: swap buttons
        try:
            self.brec.pack_forget()
            self.bstop.pack(side="left", padx=(18, 12), pady=16, before=self.btr)
            self.lstatus.configure(text="GRABANDO")
            self.btr.configure(state="disabled")
            self.bts.configure(state="disabled")
            self.bpdf.configure(state="disabled")
            self.bdocx.configure(state="disabled")
            self.bdocs.configure(state="disabled")
            self._disable_adapt_buttons()
            self._cleartxt()
            self._clear_adapt()
            self._apptxt(
                f"Grabacion iniciada...\n"
                f"Perfil: {self.pipeline.profile}\n"
                "Manten silencio los primeros segundos para perfil de ruido.\n\n"
            )
        except Exception:
            pass

        self.t0rec = time.time()
        self._updtimer()

        # Lanzar threads de captura y flusher
        try:
            threading.Thread(target=self.recloop, daemon=True).start()
            self._flusher_thread = threading.Thread(
                target=self.rec_flusher, daemon=True
            )
            self._flusher_thread.start()
        except Exception as e:
            self.recording = False
            try:
                self._rec_fp.close()
            except Exception:
                pass
            self._msg("error", "Grabacion", f"No se pudo iniciar: {str(e)[:60]}")
            return

        if self._mpl_available():
            self._updviz()
        self._updvu()

    def stoprec(self):
        """Detiene la grabacion de forma idempotente.

        Un doble clic en 'Detener' no lanza dos _procsave en paralelo.
        Espera a que el flusher termine antes de decidir si hubo audio.
        """
        if getattr(self, "_stop_done", False):
            return
        self._stop_done = True
        self.recording = False
        self.stop_ev.set()

        # Proteger la UI
        try:
            self.bstop.pack_forget()
            self.brec.pack(side="left", padx=(18, 12), pady=16, before=self.btr)
            self.lstatus.configure(text="Procesando audio profesional...")
            self.ltime.configure(text="")
        except Exception:
            pass

        # Apagar medidor VU
        try:
            self.vu_bar.set(0)
            self.vu_lbl.configure(text="-inf dB")
            self.vu_warn.configure(text="")
            if hasattr(self, "vu_hist"):
                self.vu_hist.delete("all")
        except Exception:
            pass

        # Esperar flusher
        if getattr(self, "_flusher_thread", None):
            try:
                self._flusher_thread.join(timeout=10)
            except Exception:
                pass
            self._flusher_thread = None

        # Verificar si hubo audio
        if self._rec_bytes == 0 and not self.buffer:
            self.lstatus.configure(text="No se capturo audio")
            try:
                self._rec_fp.close()
            except Exception:
                pass
            try:
                if os.path.exists(getattr(self, "_rec_raw_path", "")):
                    os.remove(self._rec_raw_path)
                    self._rec_raw_path = ""
            except Exception:
                pass
            self._stop_done = False
            return

        threading.Thread(target=self._procsave, daemon=True).start()

    def recloop(self):
        """Loop de captura de audio via PortAudio.

        El callback es lo mas ligero posible: solo copia el bloque a
        la lista. El buffer visual se reconstruye en el hilo principal
        (_updviz) y un flusher lo va volcando a disco en paralelo.
        Si el microfono es debil (config mic_gain > 1), aplica boost
        de ganancia automaticamente para mejorar la senal.
        """
        # Ganancia configurable (1.0 = sin boost, 2.0-5.0 para mics debiles)
        gain = 1.0
        try:
            cfg_gain = (getattr(self, "config", None) or {}).get("mic_gain", 1.0)
            gain = max(1.0, min(10.0, float(cfg_gain)))
        except Exception:
            pass

        def cb(indata, frames, ti, status):
            if status and status.input_overflow:
                self._audio_overflows += 1
            if self.recording:
                data = indata.flatten()
                # Aplicar ganancia si es mayor que 1.0
                if gain > 1.0:
                    data = np.clip(data * gain, -1.0, 1.0).astype(np.float32)
                self.buffer.append(data)

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
                blocksize=CHUNK_SIZE, callback=cb,
                device=mic_device_id_for(getattr(self, "config", None) or {})
            ):
                self.stop_ev.wait()
        except Exception as e:
            self.q.put(("status", f"Error: {str(e)[:40]}"))
            self.recording = False

    def rec_flusher(self):
        """Vuelca el audio grabado a disco por tramos.

        En RAM solo se conservan las ultimas ~2s (para el waveform);
        el resto se escribe como float32 crudo al archivo temporal.
        Al detener, vuelta el resto y cierra.
        """
        KEEP = int(np.ceil(VISUAL_SAMPLES / CHUNK_SIZE)) + 4  # ~2s + margen
        try:
            while self.recording:
                time.sleep(1.0)
                n = len(self.buffer)
                if n > KEEP:
                    cut = n - KEEP
                    arr = np.concatenate(self.buffer[:cut]).flatten()
                    self._rec_fp.write(
                        np.ascontiguousarray(arr, dtype=np.float32).tobytes()
                    )
                    self._rec_bytes += len(arr) * 4
                    del self.buffer[:cut]
            # Vaciado final al detener
            if self.buffer:
                arr = np.concatenate(self.buffer).flatten()
                self._rec_fp.write(
                    np.ascontiguousarray(arr, dtype=np.float32).tobytes()
                )
                self._rec_bytes += len(arr) * 4
                self.buffer = []
        except Exception:
            pass
