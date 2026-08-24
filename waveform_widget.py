#!/usr/bin/env python3
"""
waveform_widget.py — Widget de visualización de onda de audio con player
=========================================================================

Widget de Tkinter/CTk que muestra:
  - Forma de onda del audio con colores de paleta
  - Barra de progreso de reproducción
  - Controles: play/pause, stop, seek
  - Tiempo actual / duración total
  - Click para buscar posición

Uso:
    from waveform_widget import WaveformPlayer

    player = WaveformPlayer(parent, palette=C)
    player.load("grabacion.wav")
    player.pack(fill="x")
"""

import os
import threading
import time
from collections.abc import Callable

import numpy as np

try:
    import customtkinter as ctk

    CTK = True
except ImportError:
    CTK = False

import tkinter as tk


class WaveformPlayer:
    """Widget de player de audio con visualización de waveform.

    Muestra la forma de onda del audio con barra de progreso y controles.
    """

    def __init__(self, parent, palette: dict = None, on_play: Callable = None, on_stop: Callable = None, **kwargs):
        """Inicializa el widget.

        Args:
            parent: Widget padre de Tkinter.
            palette: Diccionario de colores de la paleta activa.
            on_play: Callback cuando se inicia/pausa la reproducción.
            on_stop: Callback cuando se detiene la reproducción.
        """
        self.parent = parent
        self.C = palette or {}
        self.on_play = on_play
        self.on_stop = on_stop

        # Estado del player
        self.audio_data = None
        self.sample_rate = 16000
        self.duration = 0.0
        self.is_playing = False
        self.is_paused = False
        self.current_position = 0.0  # segundos
        self._play_thread = None
        self._stop_event = threading.Event()

        # Cache del waveform
        self._waveform_cache = None
        self._waveform_width = 0

        # Construir UI
        self._build_ui()

    def _build_ui(self):
        """Construye la interfaz del widget."""
        C = self.C

        # Frame principal
        self.frame = tk.Frame(self.parent, bg=C.get("card", "#1E293B"))

        # Título del archivo
        self.title_lbl = tk.Label(
            self.frame,
            text="Sin archivo seleccionado",
            font=("Segoe UI", 10),
            bg=C.get("card", "#1E293B"),
            fg=C.get("muted", "#94A3B8"),
            anchor="w",
        )
        self.title_lbl.pack(fill="x", padx=10, pady=(8, 2))

        # Canvas del waveform
        self.waveform_canvas = tk.Canvas(
            self.frame,
            height=60,
            bg=C.get("bg", "#0F172A"),
            highlightthickness=0,
            cursor="hand2",
        )
        self.waveform_canvas.pack(fill="x", padx=10, pady=(0, 5))

        # Bind click para seek
        self.waveform_canvas.bind("<Button-1>", self._on_waveform_click)
        self.waveform_canvas.bind("<B1-Motion>", self._on_waveform_drag)
        self.waveform_canvas.bind("<Configure>", self._on_waveform_resize)

        # Barra de controles
        controls_frame = tk.Frame(self.frame, bg=C.get("card", "#1E293B"))
        controls_frame.pack(fill="x", padx=10, pady=(0, 8))

        # Botón Play/Pause
        self.play_btn = tk.Button(
            controls_frame,
            text="▶",
            font=("Segoe UI", 14),
            bg=C.get("accent", "#60A5FA"),
            fg=C.get("bg", "#0F172A"),
            activebackground=C.get("accent_hover", "#3B82F6"),
            activeforeground=C.get("bg", "#0F172A"),
            relief="flat",
            width=3,
            command=self._toggle_play,
        )
        self.play_btn.pack(side="left", padx=(0, 5))

        # Botón Stop
        self.stop_btn = tk.Button(
            controls_frame,
            text="⏹",
            font=("Segoe UI", 12),
            bg=C.get("button", "#334155"),
            fg=C.get("text", "#E2E8F0"),
            activebackground=C.get("border", "#64748B"),
            relief="flat",
            width=3,
            command=self.stop,
        )
        self.stop_btn.pack(side="left", padx=(0, 10))

        # Label de tiempo
        self.time_lbl = tk.Label(
            controls_frame,
            text="0:00 / 0:00",
            font=("Consolas", 10),
            bg=C.get("card", "#1E293B"),
            fg=C.get("text", "#E2E8F0"),
        )
        self.time_lbl.pack(side="left", padx=(0, 10))

        # Barra de progreso (scale)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_scale = tk.Scale(
            controls_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.progress_var,
            showvalue=False,
            bg=C.get("card", "#1E293B"),
            fg=C.get("text", "#E2E8F0"),
            troughcolor=C.get("button", "#334155"),
            highlightthickness=0,
            sliderrelief="flat",
            length=200,
            command=self._on_progress_change,
        )
        self.progress_scale.pack(side="left", fill="x", expand=True)

        # Volumen (opcional)
        self.volume_lbl = tk.Label(
            controls_frame,
            text="🔊",
            font=("Segoe UI", 10),
            bg=C.get("card", "#1E293B"),
            fg=C.get("text", "#E2E8F0"),
        )
        self.volume_lbl.pack(side="right", padx=(5, 0))

    def load(self, audio_path: str):
        """Carga un archivo de audio para reproducción.

        Args:
            audio_path: Ruta al archivo de audio (WAV, MP3, etc).
        """
        if not os.path.exists(audio_path):
            return

        self.stop()

        try:
            # Intentar cargar con scipy (WAV)
            from scipy.io import wavfile

            sr, data = wavfile.read(audio_path)

            # Convertir a float32
            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32767.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483647.0

            # Si es estéreo, convertir a mono
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            self.audio_data = data
            self.sample_rate = sr
            self.duration = len(data) / sr

            # Actualizar título
            filename = os.path.basename(audio_path)
            self.title_lbl.configure(text=filename)

            # Generar waveform
            self._generate_waveform()

            # Actualizar tiempo
            self._update_time_label()

        except Exception as e:
            print(f"Error cargando audio: {e}")

    def _generate_waveform(self):
        """Genera la visualización del waveform."""
        if self.audio_data is None:
            return

        # Downsample para visualización
        target_points = max(200, self.waveform_canvas.winfo_width())

        if len(self.audio_data) <= target_points:
            waveform = self.audio_data
        else:
            # Promediar bloques
            block_size = len(self.audio_data) // target_points
            waveform = np.array(
                [
                    np.max(np.abs(self.audio_data[i : i + block_size]))
                    for i in range(0, len(self.audio_data), block_size)
                ]
            )[:target_points]

        # Normalizar
        max_val = np.max(waveform) if len(waveform) > 0 else 1.0
        if max_val > 0:
            waveform = waveform / max_val

        self._waveform_cache = waveform
        self._draw_waveform()

    def _draw_waveform(self, play_position: float = 0.0):
        """Dibuja el waveform en el canvas.

        Args:
            play_position: Posición actual de reproducción (0.0 a 1.0).
        """
        if self._waveform_cache is None:
            return

        canvas = self.waveform_canvas
        C = self.C

        canvas.delete("all")

        width = canvas.winfo_width()
        height = canvas.winfo_height()

        if width < 10 or height < 10:
            return

        waveform = self._waveform_cache

        # Colores
        played_color = C.get("accent", "#60A5FA")
        unplayed_color = C.get("border", "#64748B")
        center_line = C.get("muted", "#94A3B8")

        # Línea central
        canvas.create_line(
            0,
            height // 2,
            width,
            height // 2,
            fill=center_line,
            width=1,
            dash=(2, 4),
        )

        # Dibujar waveform
        bar_width = max(1, width / len(waveform))
        play_x = int(play_position * width)

        for i, amplitude in enumerate(waveform):
            x = i * bar_width
            bar_height = int(amplitude * (height - 4) / 2)

            # Color según posición
            color = played_color if x <= play_x else unplayed_color

            # Dibujar barra (simétrica alrededor del centro)
            y_center = height // 2
            canvas.create_rectangle(
                x,
                y_center - bar_height,
                x + bar_width - 1,
                y_center + bar_height,
                fill=color,
                outline="",
            )

        # Línea de posición actual
        if play_position > 0:
            canvas.create_line(
                play_x,
                0,
                play_x,
                height,
                fill=played_color,
                width=2,
            )

    def _on_waveform_click(self, event):
        """Maneja click en el waveform para seek."""
        if self.duration <= 0:
            return

        width = self.waveform_canvas.winfo_width()
        position = event.x / width
        position = max(0.0, min(1.0, position))

        self.current_position = position * self.duration
        self.progress_var.set(position * 100)
        self._draw_waveform(position)
        self._update_time_label()

    def _on_waveform_drag(self, event):
        """Maneja drag en el waveform para seek continuo."""
        self._on_waveform_click(event)

    def _on_waveform_resize(self, event):
        """Redibuja el waveform al cambiar el tamaño."""
        self._generate_waveform()
        if self.duration > 0:
            self._draw_waveform(self.current_position / self.duration)

    def _on_progress_change(self, value):
        """Callback cuando cambia la barra de progreso."""
        if self.duration <= 0:
            return

        position = float(value) / 100.0
        self.current_position = position * self.duration
        self._draw_waveform(position)
        self._update_time_label()

    def _update_time_label(self):
        """Actualiza el label de tiempo."""
        current = self._format_time(self.current_position)
        total = self._format_time(self.duration)
        self.time_lbl.configure(text=f"{current} / {total}")

    def _format_time(self, seconds: float) -> str:
        """Formatea segundos a M:SS."""
        if seconds < 0:
            seconds = 0
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"

    def _toggle_play(self):
        """Alterna entre play y pause."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """Inicia la reproducción."""
        if self.audio_data is None or self.duration <= 0:
            return

        if self.is_paused:
            # Reanudar desde la posición actual
            self.is_paused = False
            self.is_playing = True
            self.play_btn.configure(text="⏸")
            self._start_playback_thread()
            return

        # Iniciar desde el principio o posición actual
        self.is_playing = True
        self.is_paused = False
        self._stop_event.clear()
        self.play_btn.configure(text="⏸")

        self._start_playback_thread()

        if self.on_play:
            self.on_play()

    def pause(self):
        """Pausa la reproducción."""
        self.is_paused = True
        self.is_playing = False
        self.play_btn.configure(text="▶")
        self._stop_event.set()

    def stop(self):
        """Detiene la reproducción."""
        self.is_playing = False
        self.is_paused = False
        self._stop_event.set()
        self.play_btn.configure(text="▶")

        # Resetear posición
        self.current_position = 0.0
        self.progress_var.set(0)
        self._draw_waveform(0.0)
        self._update_time_label()

        if self.on_stop:
            self.on_stop()

    def _start_playback_thread(self):
        """Inicia el hilo de reproducción."""
        if self._play_thread and self._play_thread.is_alive():
            return

        self._play_thread = threading.Thread(
            target=self._playback_worker,
            daemon=True,
        )
        self._play_thread.start()

    def _playback_worker(self):
        """Hilo de reproducción de audio."""
        try:
            import sounddevice as sd

            # Calcular chunk para streaming
            chunk_size = int(0.1 * self.sample_rate)  # 100ms chunks

            # Índice de inicio
            start_idx = int(self.current_position * self.sample_rate)
            start_idx = min(start_idx, len(self.audio_data) - 1)

            # Reproducir
            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
            ) as stream:
                i = start_idx

                while i < len(self.audio_data) and not self._stop_event.is_set():
                    chunk = self.audio_data[i : i + chunk_size]

                    if len(chunk) > 0:
                        stream.write(chunk.reshape(-1, 1))

                    i += chunk_size

                    # Actualizar posición
                    self.current_position = i / self.sample_rate
                    position_pct = self.current_position / self.duration

                    # Actualizar UI (thread-safe)
                    try:
                        self.progress_var.set(position_pct * 100)
                        self._draw_waveform(position_pct)
                        self._update_time_label()
                    except Exception:
                        pass

                    time.sleep(0.05)  # Pequeña pausa para no saturar CPU

            # Reproducción completada
            if not self._stop_event.is_set():
                self.stop()

        except ImportError:
            print("sounddevice no instalado - reproducción no disponible")
            self.stop()
        except Exception as e:
            print(f"Error en reproducción: {e}")
            self.stop()

    def set_palette(self, palette: dict):
        """Actualiza la paleta de colores."""
        self.C = palette

        # Actualizar colores de widgets
        C = palette
        self.frame.configure(bg=C.get("card", "#1E293B"))
        self.title_lbl.configure(bg=C.get("card", "#1E293B"), fg=C.get("muted", "#94A3B8"))
        self.waveform_canvas.configure(bg=C.get("bg", "#0F172A"))

        self.play_btn.configure(
            bg=C.get("accent", "#60A5FA"),
            fg=C.get("bg", "#0F172A"),
            activebackground=C.get("accent_hover", "#3B82F6"),
        )
        self.stop_btn.configure(
            bg=C.get("button", "#334155"),
            fg=C.get("text", "#E2E8F0"),
            activebackground=C.get("border", "#64748B"),
        )
        self.time_lbl.configure(bg=C.get("card", "#1E293B"), fg=C.get("text", "#E2E8F0"))
        self.volume_lbl.configure(bg=C.get("card", "#1E293B"), fg=C.get("text", "#E2E8F0"))

        # Redibujar waveform
        self._draw_waveform(self.current_position / self.duration if self.duration > 0 else 0)

    def pack(self, **kwargs):
        """Empaqueta el widget."""
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        """Ubica el widget en grid."""
        self.frame.grid(**kwargs)

    def destroy(self):
        """Destruye el widget."""
        self.stop()
        self.frame.destroy()
