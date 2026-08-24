"""
update_dialog_ui.py — Diálogo de actualización extraído de audioclass_v91.py
==============================================================================

Mixin ``UpdateDialogMixin`` que encapsula el diálogo de actualización con
notas de release formateadas, barra de progreso y descarga/instalación.

Patrón idéntico a ``ConfigDialogMixin``: el mixin asume que ``self``
tiene los atributos que ``App`` ya expone (``self._C``, ``self._lbl()``,
``self._frame()``, ``self._btn()``, ``self.q``, etc.).

Uso::

    from update_dialog_ui import UpdateDialogMixin

    class App(UpdateDialogMixin, ...):
        ...

    app._show_update_dialog("9.2.0", "https://github.com/...")
"""

from __future__ import annotations

import re
import threading
import tkinter as tk
from typing import TYPE_CHECKING, Optional

try:
    import customtkinter as ctk

    CTK = True
except ImportError:
    CTK = False

if TYPE_CHECKING:
    pass


class UpdateDialogMixin:
    """Mixin que proporciona el diálogo de actualización con release notes."""

    def _show_update_dialog(
        self,
        latest_version: str,
        release_url: str,
        release_notes: str = "",
    ) -> None:
        """Muestra diálogo de actualización con opción de descargar e instalar.

        Args:
            latest_version: Versión más reciente disponible.
            release_url: URL de la release en GitHub.
            release_notes: Notas de la release (texto con formato markdown básico).
        """
        C = self._C

        top = ctk.CTkToplevel(self) if CTK else tk.Toplevel(self)
        top.title("Actualización disponible")
        top.geometry("520x520")
        top.transient(self)
        top.grab_set()

        # Título
        self._lbl(
            top,
            "¡Nueva versión disponible!",
            font=(self.FH, 16, "bold"),
            text_color=C["ok"],
        ).pack(pady=(15, 5))
        self._lbl(
            top,
            f"v{latest_version}  (actual: v{self._app_version()})",
            font=(self.FB, 12),
            text_color=C["text"],
        ).pack(pady=(0, 10))

        # Notas de la release (scrollable con formato mejorado)
        notes_frame = self._frame(top, fg_color=C["card"])
        notes_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Formatear release notes (markdown básico → texto legible)
        formatted_notes = self._format_release_notes(release_notes)

        notes_text = tk.Text(
            notes_frame,
            font=(self.FB, 10),
            bg=C["card"],
            fg=C["text"],
            wrap="word",
            relief="flat",
            highlightthickness=0,
            padx=12,
            pady=10,
            state="normal",
        )

        # Scrollbar para las notas
        notes_scroll = tk.Scrollbar(notes_frame, command=notes_text.yview)
        notes_text.configure(yscrollcommand=notes_scroll.set)

        notes_text.pack(side="left", fill="both", expand=True)
        notes_scroll.pack(side="right", fill="y")

        # Insertar texto formateado con tags
        self._insert_formatted_notes(notes_text, formatted_notes, C, top)
        notes_text.configure(state="disabled")  # Solo lectura

        # Link a GitHub
        if release_url:

            def _open_url():
                import webbrowser

                webbrowser.open(release_url)

            self._btn(
                top,
                "Ver novedades en GitHub",
                _open_url,
                width=200,
                height=28,
                fg_color=C["button"],
                text_color=C["text"],
            ).pack(pady=(0, 10))

    def _app_version(self) -> str:
        """Obtiene la versión de la app. Override en App si es necesario."""
        try:
            from audioclass_core import APP_VER

            return APP_VER
        except ImportError:
            return "unknown"

    def _format_release_notes(self, notes: str) -> list[tuple[str, str]]:
        """Formatea release notes de markdown básico a estructura legible.

        Returns:
            Lista de tuplas (tipo, texto) donde tipo es:
            'header', 'bullet', 'text', 'separator', 'blank', 'bold'
        """
        if not notes or not notes.strip():
            return [("text", "No hay notas de disponibles.")]

        lines = notes.strip().split("\n")
        formatted = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                formatted.append(("blank", ""))
            elif stripped.startswith("---") or stripped.startswith("==="):
                formatted.append(("separator", ""))
            elif stripped.startswith("## "):
                formatted.append(("header", stripped[3:]))
            elif stripped.startswith("# "):
                formatted.append(("header", stripped[2:]))
            elif stripped.startswith("- ") or stripped.startswith("* "):
                formatted.append(("bullet", stripped[2:]))
            elif stripped.startswith("**") and stripped.endswith("**"):
                formatted.append(("bold", stripped.strip("*")))
            else:
                # Limpiar markdown inline: **bold**, `code`, [link](url)
                clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
                clean = re.sub(r"`([^`]+)`", r"\1", clean)
                clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
                formatted.append(("text", clean))

        return formatted

    def _insert_formatted_notes(
        self,
        text_widget,
        formatted: list[tuple[str, str]],
        C: dict,
        parent=None,
    ) -> None:
        """Inserta las release notes formateadas en el widget de texto."""
        # Definir tags de estilo
        text_widget.tag_configure("header", font=(self.FH, 11, "bold"), foreground=C["accent"])
        text_widget.tag_configure("bold", font=(self.FB, 10, "bold"), foreground=C["text"])
        text_widget.tag_configure(
            "bullet",
            font=(self.FB, 10),
            foreground=C["text"],
            lmargin1=20,
            lmargin2=36,
        )
        text_widget.tag_configure("text", font=(self.FB, 10), foreground=C["text"])
        text_widget.tag_configure("muted", font=(self.FB, 10), foreground=C["muted"])
        text_widget.tag_configure("separator", font=(self.FB, 10), foreground=C["border"])

        for kind, content in formatted:
            if kind == "blank":
                text_widget.insert("end", "\n")
            elif kind == "separator":
                text_widget.insert("end", "─" * 40 + "\n", "separator")
            elif kind == "header":
                text_widget.insert("end", f"{content}\n", "header")
            elif kind == "bullet":
                text_widget.insert("end", f"  • {content}\n", "bullet")
            elif kind == "bold":
                text_widget.insert("end", f"{content}\n", "bold")
            else:
                text_widget.insert("end", f"{content}\n", "text")

        # Barra de progreso (oculta inicialmente)
        progress_var = tk.DoubleVar(value=0)
        _parent = parent or self
        progress_bar = ctk.CTkProgressBar(
            _parent,
            width=400,
            height=12,
            variable=progress_var,
            progress_color=C["ok"],
        )
        progress_lbl = self._lbl(_parent, "", font=(self.FB, 10), text_color=C["muted"])

        # Botones
        btn_frame = self._frame(_parent, fg_color="transparent")
        btn_frame.pack(pady=(10, 15))

        def _do_update():
            """Descarga e instala la actualización."""
            btn_download.configure(state="disabled", text="Descargando...")
            btn_skip.configure(state="disabled")
            progress_bar.pack(pady=(0, 5))
            progress_lbl.pack(pady=(0, 10))

            def _worker():
                try:
                    from update_checker import (
                        check_for_updates,
                        download_update,
                        find_download_asset,
                        install_update,
                        verify_download,
                    )

                    # Buscar asset correcto
                    result = check_for_updates(self._app_version())
                    asset = find_download_asset(result.get("assets", []))

                    if not asset:
                        self.q.put(("update_error", "No se encontró el archivo de actualización"))
                        return

                    # Descargar
                    def _on_progress(downloaded, total, msg):
                        if total > 0:
                            progress_var.set(downloaded / total)
                        self.q.put(("update_progress", msg))

                    file_path, error = download_update(asset, on_progress=_on_progress)

                    if error:
                        self.q.put(("update_error", error))
                        return

                    # Verificar
                    self.q.put(("update_progress", "Verificando integridad..."))
                    ok, msg = verify_download(file_path, sha256_url=result.get("sha256_url"))
                    if not ok:
                        self.q.put(("update_error", f"Verificación falló: {msg}"))
                        return

                    # Instalar
                    self.q.put(("update_progress", "Instalando actualización..."))
                    success, msg = install_update(file_path)

                    if success:
                        self.q.put(("update_installed", msg))
                    else:
                        self.q.put(("update_error", msg))

                except Exception as e:
                    self.q.put(("update_error", str(e)[:100]))

            threading.Thread(target=_worker, daemon=True).start()

        def _do_later():
            _parent.destroy()

        btn_download = self._btn(
            btn_frame,
            "Descargar e instalar",
            _do_update,
            width=180,
            height=36,
            fg_color=C["ok"],
            hover_color=C["accent"],
        )
        btn_download.pack(side="left", padx=(0, 10))
        btn_skip = self._btn(
            btn_frame,
            "Ahora no",
            _do_later,
            width=120,
            height=36,
            fg_color=C["button"],
            text_color=C["text"],
        )
        btn_skip.pack(side="left")

        # Guardar referencias para que _poll pueda actualizar la UI
        self._update_dialog = _parent
        self._update_progress_var = progress_var
        self._update_progress_bar = progress_bar
        self._update_progress_lbl = progress_lbl
        self._update_btn_download = btn_download
        self._update_btn_skip = btn_skip
