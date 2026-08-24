#!/usr/bin/env python3
"""
mic_optimizer_ui.py — Mixin de prueba y optimización de micrófono
=================================================================
Extrae las ventanas de prueba de micrófono y optimizador de
audioclass_v91.py en un mixin independiente.

El mixin asume que la clase que lo hereda tiene:
    - self.config: dict de configuración
    - self.pipeline: AudioPipeline para procesamiento
    - self.q: queue.Queue para mensajes UI
    - self._lbl(), self._btn(), self._frame(): helpers de UI
    - self.FH, self.FB: fuentes tipográficas
    - self._mic_device_id_for(): resolver id del micrófono
    - self._same_mic(): comparar nombres de micrófono
    - self._find_best_mic(): auto-detectar mejor micrófono
    - self._input_devices(): listar dispositivos de entrada
    - self._open_mic_opt(): ventana del optimizador (llamado desde warning)

Uso:
    class App(MicTestMixin, ...):
        pass
"""

import sys
import threading
import time

import numpy as np
from scipy import signal

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import customtkinter as ctk

    CTK = True
except ImportError:
    CTK = False

try:
    import tkinter.ttk as ttk
except ImportError:
    pass


# ── Constantes de audio (misma fuente que audioclass_core.py) ─────────────
SAMPLE_RATE = 16000


class MicTestMixin:
    """Mixin que proporciona ventanas de prueba y optimización de micrófono.

    Métodos principales:
        open_mic_test(): Abre la ventana de prueba rápida (8s).
        open_mic_optimizer(): Abre el optimizador de micrófono.
        mic_test_worker(): Hilo de grabación + métricas de prueba.
        mic_opt_worker(): Hilo de diagnóstico/optimización.
    """

    def open_mic_test(self):
        """Ventana de prueba nativa del microfono: graba ~8 s con el pipeline
        activo, muestra un medidor de nivel en vivo y las métricas de calidad."""
        from audioclass_v91 import CTK as _CTK
        from audioclass_v91 import ctk as _ctk

        # Reutilizar ventana si ya está abierta
        if getattr(self, "mic_test_top", None) is not None:
            try:
                if self.mic_test_top.winfo_exists():
                    self.mic_test_top.lift()
                    self.mic_test_top.focus_force()
                    return
            except Exception:
                pass

        top = _ctk.CTkToplevel(self) if _CTK else _ctk.Toplevel(self)
        top.title("Prueba de Microfono")
        top.geometry("600x440")
        top.transient(self)
        top.grab_set()
        self.mic_test_top = top
        self._mic_busy = False

        self._lbl(top, "Prueba rapida de microfono", font=(self.FH, 18, "bold"), text_color=self._C["accent"]).pack(
            pady=(18, 4)
        )
        self._lbl(
            top,
            "Pulsa el boton, espera 2 segundos y habla durante ~6 segundos.",
            font=(self.FB, 12),
            text_color=self._C["muted"],
        ).pack(pady=(0, 12))

        lvl_row = self._frame(top, fg_color="transparent")
        lvl_row.pack(fill="x", padx=30, pady=(0, 4))
        self._lbl(lvl_row, "Nivel:", font=(self.FB, 11)).pack(side="left", padx=(0, 8))
        if _CTK:
            self.mic_lvl_bar = _ctk.CTkProgressBar(lvl_row, height=14, corner_radius=7, progress_color=self._C["muted"])
        else:
            self.mic_lvl_bar = ttk.Progressbar(lvl_row, mode="determinate", maximum=100)
        self.mic_lvl_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.mic_lvl_lbl = self._lbl(lvl_row, "-∞ dB", font=(self.FB, 10), text_color=self._C["muted"])
        self.mic_lvl_lbl.pack(side="left")

        self.mic_state = self._lbl(top, "", font=(self.FB, 12), text_color=self._C["warn"])
        self.mic_state.pack(pady=(8, 4))

        self.mic_result = self._lbl(top, "", font=(self.FB, 11), text_color=self._C["text"], anchor="w", wraplength=540)
        self.mic_result.pack(padx=30, pady=(4, 10))

        self.btn_mic_test = self._btn(
            top,
            "Comenzar prueba (8 s)",
            self._mic_test_start_inner,
            width=280,
            height=44,
            font=(self.FB, 14, "bold"),
            fg_color=self._C["err"],
            hover_color=self._C["err"],
        )
        self.btn_mic_test.pack(pady=(4, 8))
        self._btn(top, "Cerrar", top.destroy, width=140, height=36).pack(pady=(0, 14))

    def _mic_test_start_inner(self):
        """Arranca la grabación de prueba en un hilo."""
        try:
            if getattr(self, "_mic_busy", False):
                return
            self._mic_busy = True
            if hasattr(self, "btn_mic_test") and self.btn_mic_test.winfo_exists():
                self.btn_mic_test.configure(state="disabled", text="Escuchando... habla ahora")
            if hasattr(self, "mic_state") and self.mic_state.winfo_exists():
                self.mic_state.configure(text="HABLA AHORA durante ~6 segundos", text_color=self._C["err"])
            if hasattr(self, "mic_result") and self.mic_result.winfo_exists():
                self.mic_result.configure(text="")
            threading.Thread(target=self._mic_test_worker_inner, daemon=True).start()
        except Exception:
            self._mic_busy = False

    def _mic_test_worker_inner(self):
        """Hilo de prueba: graba ~8s, procesa con el pipeline, envía métricas."""
        try:
            from audioclass_v91 import SAMPLE_RATE as SR
            from audioclass_v91 import _mic_device_id_for

            DUR = 8
            win = int(0.1 * SR)
            buf = []

            def cb(indata, frames, ti, status):
                x = indata.copy().flatten()
                buf.append(x)
                r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if len(x) else 0.0
                self.q.put(("mic_lvl", r))

            with sd.InputStream(
                samplerate=SR,
                channels=1,
                dtype=np.float32,
                blocksize=win,
                callback=cb,
                device=_mic_device_id_for(getattr(self, "config", None) or {}),
            ):
                t0 = time.time()
                while time.time() - t0 < DUR:
                    time.sleep(0.05)

            if not buf:
                self.q.put(("mic_result", "No se capturo audio del microfono."))
                return
            raw = np.concatenate(buf).flatten()
            proc = self.pipeline.process(raw)
            self.q.put(("mic_result", self._compute_mic_metrics(raw, proc)))
        except Exception as e:
            self.q.put(("mic_result", f"Error: {e}"))
        finally:
            self._mic_busy = False
            self.q.put(("mic_idle", None))

    def _compute_mic_metrics(self, raw, proc):
        """Calcula métricas objetivas raw vs mejorado."""
        from audioclass_v91 import SAMPLE_RATE as SR

        w = int(0.04 * SR)
        hop = w // 2
        fr_r = self.pipeline._frame_rms(raw.astype(np.float64), w, hop)
        fr_p = self.pipeline._frame_rms(proc.astype(np.float64), w, hop)
        if len(fr_r) == 0 or len(fr_p) == 0:
            return "Audio demasiado corto para analizar."
        floor_r = float(np.percentile(fr_r, 10))
        speech_r = float(np.percentile(fr_r, 90))
        speech_p = float(np.percentile(fr_p, 90))
        QUIET = 0.01
        sil_r = float(np.mean(fr_r < QUIET)) * 100
        sil_p = float(np.mean(fr_p < QUIET)) * 100

        def band(x, lo, hi):
            if len(x) < 512:
                return 0.0
            f, P = signal.welch(x, fs=SR, nperseg=2048)
            return float(np.sum(P[(f >= lo) & (f <= hi)]))

        vi, vo = band(raw, 200, 3000), band(proc, 200, 3000)
        hii, hoo = band(raw, 7100, 7900), band(proc, 7100, 7900)
        pk = float(np.max(np.abs(proc))) if len(proc) else 0.0
        floor_p = float(np.percentile(fr_p, 10))
        snr = speech_p / max(floor_p, 1e-12)
        spread_r = speech_r / max(floor_r, 1e-12)
        lines = []
        if speech_p > 0.02 and spread_r >= 2.0:
            lines.append(f"[OK] Voz detectada (nivel de habla {speech_p:.3f})")
        elif speech_p > 0.02:
            lines.append(
                f"Voz muy baja ({speech_p:.3f}) — sin estructura de voz (ruido amplificado); revisa el microfono"
            )
        else:
            lines.append(f"Voz muy baja ({speech_p:.3f}) — acercate al microfono o habla mas alto")
        lines.append(f"Silencio recortado: {sil_r:.0f}% -> {sil_p:.0f}% (noise gate)")
        lines.append(f"Nivel de habla: {speech_r:.4f} -> {speech_p:.4f}")
        lines.append(f"SNR habla/piso: {snr:.1f}x")
        lines.append(f"Voz 200-3000 Hz: x{vo / max(vi, 1e-12):.2f}")
        if hoo <= 1e-12:
            lines.append("Agudos 7.1-7.9 kHz: sin señal (filtrado por el perfil)")
        else:
            lines.append(f"Agudos 7.1-7.9 kHz: {20 * np.log10(hoo / max(hii, 1e-12)):+.1f} dB")
        lines.append(f"Pico: {pk:.3f} (limite {self.pipeline.p['limiter']:.2f}, sin clipping)")
        return "\n".join(lines)

    # ── Optimizador de micrófono ───────────────────────────────────────────

    def open_mic_optimizer(self):
        """Ventana del optimizador de micrófono: diagnostica el nivel de
        entrada y puede aplicar corrección (nivel 100% + desmute + boost)."""
        from audioclass_v91 import CTK as _CTK
        from audioclass_v91 import _input_devices
        from audioclass_v91 import ctk as _ctk

        if getattr(self, "mic_opt_top", None) is not None:
            try:
                if self.mic_opt_top.winfo_exists():
                    self.mic_opt_top.lift()
                    self.mic_opt_top.focus_force()
                    return
            except Exception:
                pass

        top = _ctk.CTkToplevel(self) if _CTK else _ctk.Toplevel(self)
        top.title("Optimizador de micrófono")
        top.geometry("680x600")
        top.transient(self)
        top.grab_set()
        self.mic_opt_top = top

        self._lbl(top, "Optimizador de micrófono", font=(self.FH, 18, "bold"), text_color=self._C["accent"]).pack(
            pady=(16, 4)
        )
        self._lbl(
            top,
            "Diagnostica el nivel de entrada y corrige las grabaciones en silencio. "
            "Habla en voz alta durante cada prueba de 4 segundos.",
            font=(self.FB, 11),
            text_color=self._C["muted"],
            wraplength=620,
        ).pack(pady=(0, 10))

        mic_row = self._frame(top, fg_color="transparent")
        mic_row.pack(fill="x", padx=30, pady=(0, 6))
        self._lbl(mic_row, "Micrófono:", font=(self.FB, 11)).pack(side="left", padx=(0, 8))
        mic_devs = _input_devices()
        mic_names = ["Predeterminado del sistema"] + [n for _, n in mic_devs]
        cfg_mic = str((getattr(self, "config", None) or {}).get("mic_device") or "").strip()
        self.mic_opt_mic_var = _ctk.StringVar(value=cfg_mic if cfg_mic in mic_names else "Predeterminado del sistema")
        if _CTK:
            self.mic_opt_menu = _ctk.CTkOptionMenu(
                mic_row,
                values=mic_names,
                variable=self.mic_opt_mic_var,
                width=430,
                font=(self.FB, 11),
                fg_color=self._C["button"],
                text_color=self._C["text"],
                button_color=self._C["accent"],
                button_hover_color=self._C["accent_hover"],
                dropdown_fg_color=self._C["card"],
                dropdown_hover_color=self._C["border"],
                dropdown_text_color=self._C["text"],
            )
        else:
            self.mic_opt_menu = _ctk.OptionMenu(mic_row, self.mic_opt_mic_var, *mic_names)
        self.mic_opt_menu.pack(side="left", padx=(0, 8))
        if not mic_devs:
            try:
                self.mic_opt_menu.configure(state="disabled")
            except Exception:
                pass

        lvl_row = self._frame(top, fg_color="transparent")
        lvl_row.pack(fill="x", padx=30, pady=(0, 4))
        self._lbl(lvl_row, "Nivel:", font=(self.FB, 11)).pack(side="left", padx=(0, 8))
        if _CTK:
            self.mic_opt_lvl_bar = _ctk.CTkProgressBar(
                lvl_row, height=14, corner_radius=7, progress_color=self._C["muted"]
            )
        else:
            self.mic_opt_lvl_bar = ttk.Progressbar(lvl_row, mode="determinate", maximum=100)
        self.mic_opt_lvl_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.mic_opt_lvl_lbl = self._lbl(lvl_row, "-∞ dB", font=(self.FB, 10), text_color=self._C["muted"])
        self.mic_opt_lvl_lbl.pack(side="left")

        self.mic_opt_state_lbl = self._lbl(top, "", font=(self.FB, 12), text_color=self._C["warn"])
        self.mic_opt_state_lbl.pack(pady=(6, 4))

        if _CTK:
            self.mic_opt_txt = _ctk.CTkTextbox(
                top,
                height=250,
                font=("Consolas", 10),
                text_color=self._C["text"],
                fg_color=self._C["card"],
                border_width=1,
                border_color=self._C["border"],
                wrap="word",
                state="disabled",
            )
        else:
            import tkinter as _tk

            self.mic_opt_txt = _tk.Text(
                top,
                height=16,
                font=("Consolas", 10),
                bg=self._C["card"],
                fg=self._C["text"],
                wrap="word",
                state="disabled",
                relief="flat",
                borderwidth=1,
                highlightthickness=1,
                highlightbackground=self._C["border"],
            )
        self.mic_opt_txt.pack(fill="both", expand=True, padx=30, pady=(4, 8))

        btns = self._frame(top, fg_color="transparent")
        btns.pack(fill="x", padx=30, pady=(0, 14))
        self.btn_mic_opt_diag = self._btn(
            btns,
            "Diagnosticar",
            lambda: self._mic_opt_start_inner(False),
            width=200,
            height=40,
            font=(self.FB, 12, "bold"),
            fg_color=self._C["accent"],
            hover_color=self._C["accent_hover"],
        )
        self.btn_mic_opt_diag.pack(side="left", padx=(0, 8))
        self.btn_mic_opt_apply = self._btn(
            btns,
            "Aplicar optimización",
            lambda: self._mic_opt_start_inner(True),
            width=225,
            height=40,
            font=(self.FB, 12, "bold"),
            fg_color=self._C["ok"],
            hover_color=self._C["ok"],
        )
        self.btn_mic_opt_apply.pack(side="left", padx=(0, 8))
        self._btn(btns, "Cerrar", top.destroy, width=100, height=36).pack(side="left")

    def _mic_opt_start_inner(self, do_apply):
        """Arranca el diagnóstico/optimización en un hilo."""
        try:
            if getattr(self, "_mic_opt_busy", False):
                return
            self._mic_opt_busy = True
            for b in ("btn_mic_opt_diag", "btn_mic_opt_apply"):
                w = getattr(self, b, None)
                if w is not None:
                    try:
                        if w.winfo_exists():
                            w.configure(state="disabled")
                    except Exception:
                        pass
            if hasattr(self, "mic_opt_txt"):
                try:
                    self.mic_opt_txt.configure(state="normal")
                    self.mic_opt_txt.delete("1.0", "end")
                    self.mic_opt_txt.configure(state="disabled")
                except Exception:
                    pass
            mic_name = ""
            try:
                mic_name = self.mic_opt_mic_var.get()
            except Exception:
                pass
            threading.Thread(
                target=self._mic_opt_worker_inner, args=(do_apply,), kwargs={"mic_name": mic_name}, daemon=True
            ).start()
        except Exception:
            self._mic_opt_busy = False

    def _mic_opt_worker_inner(self, do_apply, mic_name=""):
        """Hilo del optimizador: diagnostica y aplica corrección."""
        from audioclass_v91 import _mic_device_id_for, _same_mic, log_exc

        try:
            if sys.platform != "win32":
                self.q.put(("mic_opt_log", "El optimizador solo aplica en Windows.\n"))
                self.q.put(("mic_opt_done", "NO_WINDOWS"))
                return
            import optimizar_mic as om

            log = self.q.put

            target = (mic_name or "").strip()
            use_default = (not target) or target == "Predeterminado del sistema"
            dev = None
            sd_id = None
            sname = ""
            if not use_default:
                try:
                    dev = om._capture_device_by_sd_name(target)
                except Exception:
                    dev = None
                if dev is None:
                    log(("mic_opt_log", f"No pude identificar '{target}' en Windows; uso el predeterminado.\n"))
            if dev is None:
                dev = om._default_capture_device()
                try:
                    sname = sd.query_devices(sd.default.device[0])["name"]
                except Exception:
                    pass
            else:
                sname = target
                sd_id = _mic_device_id_for({"mic_device": target})
            if use_default:
                log(("mic_opt_log", f"Dispositivo por defecto: {sname}\n"))
            else:
                log(("mic_opt_log", f"Dispositivo (elegido): {sname}\n"))
            st = om.get_mic_state(dev)
            if st:
                log(("mic_opt_log", f"  Nivel: {st[0]}%  |  Mute: {'SÍ [!]' if st[1] else 'No'}\n"))
            else:
                log(("mic_opt_log", "  (nivel no accesible)\n"))

            pv = om.privacy_mic()
            if pv != "Allow":
                log(
                    (
                        "mic_opt_log",
                        f"Permiso de micrófono: {pv}  DENEGADO — permite el acceso en "
                        "Configuración > Privacidad > Micrófono\n",
                    )
                )
            else:
                log(("mic_opt_log", "Permiso de micrófono: Allow\n"))

            log(("mic_opt_log", "Microfonos activos:\n"))
            try:
                for did2, lvl, mute in om.list_mics():
                    mark = ""
                    if _same_mic(did2, sname):
                        mark = " [DEFAULT]" if use_default else " [ELEGIDO]"
                    extra = f"nivel {lvl}%" + (" mute [!]" if mute else "")
                    log(("mic_opt_log", f"  {extra}{mark}  {str(did2)[:64]}\n"))
            except Exception as e:
                log(("mic_opt_log", f"  (no enumerable: {e})\n"))

            self.q.put(("mic_opt_state", "HABLA AHORA durante 4 s"))
            antes = om.measure_signal(4.0, device=sd_id, on_level=lambda r: self.q.put(("mic_opt_lvl", r)))
            self.q.put(("mic_opt_state", ""))
            log(
                (
                    "mic_opt_log",
                    f"Prueba: {antes['dur']:.1f}s | piso {antes['piso']:.4f} | "
                    f"p90 {antes['p90']:.4f} | peak {antes['peak']:.3f} -> {antes['veredicto']}\n",
                )
            )
            if not do_apply:
                if antes["veredicto"] == "OK":
                    log(("mic_opt_log", "El micrófono captura bien. No se requiere optimización.\n"))
                else:
                    log(
                        (
                            "mic_opt_log",
                            "Sugerencia: pulsa 'Aplicar optimización' para subir el nivel "
                            "al 100% y activar el boost si el driver lo permite.\n",
                        )
                    )
                self.q.put(("mic_opt_done", antes["veredicto"]))
                return

            log(("mic_opt_log", "\nAPLICANDO OPTIMIZACIÓN...\n"))
            ok1, err1 = om.apply_mic_level(dev, 100)
            log(("mic_opt_log", f"  [{'OK' if ok1 else 'NO'}] nivel -> 100% + desmute  {err1}\n"))
            ok2, msg2 = om.apply_boost(dev)
            log(("mic_opt_log", f"  [{'OK' if ok2 else 'NO'}] boost del nodo de volumen  {msg2}\n"))
            time.sleep(0.5)
            st2 = om.get_mic_state(dev)
            if st2:
                log(("mic_opt_log", f"  Estado tras aplicar: nivel {st2[0]}% | mute {'SÍ [!]' if st2[1] else 'No'}\n"))

            self.q.put(("mic_opt_state", "HABLA AHORA durante 4 s (post-optimización)"))
            despues = om.measure_signal(4.0, device=sd_id, on_level=lambda r: self.q.put(("mic_opt_lvl", r)))
            self.q.put(("mic_opt_state", ""))
            log(
                (
                    "mic_opt_log",
                    f"Post: {despues['dur']:.1f}s | piso {despues['piso']:.4f} | "
                    f"p90 {despues['p90']:.4f} | peak {despues['peak']:.3f} -> {despues['veredicto']}\n",
                )
            )
            mejo = despues["p90"] / max(antes["p90"], 1e-6)
            log(("mic_opt_log", f"RESUMEN: p90 {antes['p90']:.4f} -> {despues['p90']:.4f}  (x{mejo:.1f})\n"))
            if despues["veredicto"] == "OK":
                log(("mic_opt_log", "El micrófono quedó optimizado. La app ya capturará tu voz.\n"))
            elif despues["veredicto"] == "DÉBIL":
                log(
                    (
                        "mic_opt_log",
                        "Sigue débil. Si NO hablaste en la prueba, repítela hablando. Si hablaste "
                        "y sigue débil: acércate al micro, revisa el boost en Realtek Audio Console "
                        "o desactiva la supresión de ruido agresiva.\n",
                    )
                )
            else:
                log(
                    (
                        "mic_opt_log",
                        "Sigue sin señal: revisa que el micro no esté físicamente desactivado "
                        "y que el dispositivo por defecto sea el correcto.\n",
                    )
                )
            self.q.put(("mic_opt_done", despues["veredicto"]))
        except Exception as e:
            log_exc("mic optimizer")
            try:
                self.q.put(("mic_opt_log", f"Error: {str(e)[:120]}\n"))
            except Exception:
                pass
            self.q.put(("mic_opt_done", "ERROR"))
