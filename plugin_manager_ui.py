#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plugin_manager_ui.py — Interfaz gráfica para gestionar plugins de templates
============================================================================

Proporciona widgets Tkinter/CTk para:
  - Ver plugins instalados (builtin + custom)
  - Habilitar/deshabilitar plugins
  - Crear nuevos plugins
  - Instalar plugins desde archivos
  - Exportar plugins
  - Validar plugins

Se integra en el diálogo de configuración de AudioClass.
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Dict, List, Optional, Tuple

try:
    import customtkinter as ctk
    CTK = True
except ImportError:
    CTK = False

from template_plugins import PluginManager, PluginTemplate, get_plugin_manager


# ── Colores por defecto (se sobreescriben con la paleta) ─────────────────────
DEFAULT_COLORS = {
    "bg": "#1a1a2e",
    "card": "#16213e",
    "button": "#0f3460",
    "accent": "#e94560",
    "text": "#ffffff",
    "text_dim": "#a0a0a0",
    "success": "#00c853",
    "warning": "#ff9800",
    "error": "#f44336",
}


class PluginManagerDialog:
    """Diálogo modal para gestionar plugins de templates."""

    def __init__(self, parent, palette: Optional[dict] = None):
        self.parent = parent
        self.C = palette or DEFAULT_COLORS
        self.manager = get_plugin_manager()
        self.manager.discover(force=True)

        # Crear ventana
        if CTK:
            self.dialog = ctk.CTkToplevel(parent)
        else:
            self.dialog = tk.Toplevel(parent)

        self.dialog.title("Gestor de Plugins de Templates")
        self.dialog.geometry("800x600")
        self.dialog.resizable(True, True)
        self.dialog.configure(bg=self.C.get("bg", "#1a1a2e"))

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        """Construye la interfaz del diálogo."""
        # Header
        header = tk.Frame(self.dialog, bg=self.C.get("card", "#16213e"), height=60)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        tk.Label(
            header,
            text="🔌 Gestor de Plugins",
            font=("Segoe UI", 16, "bold"),
            bg=self.C.get("card", "#16213e"),
            fg=self.C.get("text", "#ffffff"),
        ).pack(side="left", padx=15, pady=10)

        # Stats
        stats_frame = tk.Frame(header, bg=self.C.get("card", "#16213e"))
        stats_frame.pack(side="right", padx=15)

        self.stats_label = tk.Label(
            stats_frame,
            text="",
            font=("Segoe UI", 10),
            bg=self.C.get("card", "#16213e"),
            fg=self.C.get("text_dim", "#a0a0a0"),
        )
        self.stats_label.pack(side="right")

        # Toolbar
        toolbar = tk.Frame(self.dialog, bg=self.C.get("bg", "#1a1a2e"), height=40)
        toolbar.pack(fill="x", padx=10, pady=5)

        buttons = [
            ("🔄 Actualizar", self._refresh_list),
            ("➕ Crear Plugin", self._create_plugin),
            ("📥 Instalar", self._install_plugin),
            ("📁 Abrir Directorio", self._open_plugins_dir),
        ]

        for text, cmd in buttons:
            if CTK:
                btn = ctk.CTkButton(
                    toolbar, text=text, command=cmd,
                    width=120, height=30, font=("Segoe UI", 10),
                    fg_color=self.C.get("button", "#0f3460"),
                    hover_color=self.C.get("accent", "#e94560"),
                )
            else:
                btn = tk.Button(
                    toolbar, text=text, command=cmd,
                    bg=self.C.get("button", "#0f3460"),
                    fg=self.C.get("text", "#ffffff"),
                    font=("Segoe UI", 9),
                    relief="flat", padx=10, pady=4,
                )
            btn.pack(side="left", padx=3)

        # Filtro
        filter_frame = tk.Frame(self.dialog, bg=self.C.get("bg", "#1a1a2e"))
        filter_frame.pack(fill="x", padx=10, pady=2)

        tk.Label(
            filter_frame, text="Filtrar:",
            bg=self.C.get("bg", "#1a1a2e"),
            fg=self.C.get("text", "#ffffff"),
            font=("Segoe UI", 10),
        ).pack(side="left", padx=5)

        self.filter_var = tk.StringVar(value="all")
        for text, value in [("Todos", "all"), ("Incorporados", "builtin"), ("Personales", "custom")]:
            rb = tk.Radiobutton(
                filter_frame, text=text, variable=self.filter_var, value=value,
                command=self._refresh_list,
                bg=self.C.get("bg", "#1a1a2e"),
                fg=self.C.get("text", "#ffffff"),
                selectcolor=self.C.get("card", "#16213e"),
                activebackground=self.C.get("bg", "#1a1a2e"),
                activeforeground=self.C.get("text", "#ffffff"),
                font=("Segoe UI", 9),
            )
            rb.pack(side="left", padx=8)

        # Plugin list (scrollable)
        list_frame = tk.Frame(self.dialog, bg=self.C.get("bg", "#1a1a2e"))
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.canvas = tk.Canvas(
            list_frame,
            bg=self.C.get("bg", "#1a1a2e"),
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable = tk.Frame(self.canvas, bg=self.C.get("bg", "#1a1a2e"))

        self.scrollable.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Footer
        footer = tk.Frame(self.dialog, bg=self.C.get("card", "#16213e"), height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        self.status_label = tk.Label(
            footer,
            text="Listo",
            font=("Segoe UI", 9),
            bg=self.C.get("card", "#16213e"),
            fg=self.C.get("text_dim", "#a0a0a0"),
        )
        self.status_label.pack(side="left", padx=15, pady=8)

        # Close button
        if CTK:
            close_btn = ctk.CTkButton(
                footer, text="Cerrar", command=self.dialog.destroy,
                width=100, height=30, font=("Segoe UI", 10),
                fg_color=self.C.get("accent", "#e94560"),
            )
        else:
            close_btn = tk.Button(
                footer, text="Cerrar", command=self.dialog.destroy,
                bg=self.C.get("accent", "#e94560"),
                fg=self.C.get("text", "#ffffff"),
                font=("Segoe UI", 10),
                relief="flat", padx=20, pady=4,
            )
        close_btn.pack(side="right", padx=15, pady=5)

    def _refresh_list(self):
        """Actualiza la lista de plugins."""
        # Limpiar
        for widget in self.scrollable.winfo_children():
            widget.destroy()

        # Obtener templates según filtro
        filter_val = self.filter_var.get()
        if filter_val == "builtin":
            templates = self.manager.get_builtin_templates()
        elif filter_val == "custom":
            templates = self.manager.get_custom_templates()
        else:
            templates = self.manager.get_all_templates()

        # Stats
        total = len(self.manager.get_all_templates())
        enabled = len(self.manager.get_enabled_templates())
        custom = len(self.manager.get_custom_templates())
        self.stats_label.configure(text=f"{enabled}/{total} habilitados | {custom} personalizados")

        if not templates:
            tk.Label(
                self.scrollable,
                text="No hay plugins en esta categoría",
                font=("Segoe UI", 12),
                bg=self.C.get("bg", "#1a1a2e"),
                fg=self.C.get("text_dim", "#a0a0a0"),
            ).pack(pady=30)
            return

        # Renderizar cada plugin
        for tid, template in sorted(templates.items()):
            self._render_plugin_card(tid, template)

    def _render_plugin_card(self, tid: str, template: PluginTemplate):
        """Renderiza una tarjeta de plugin."""
        card_bg = self.C.get("card", "#16213e")

        card = tk.Frame(self.scrollable, bg=card_bg, relief="flat", bd=0)
        card.pack(fill="x", padx=5, pady=4)

        # Header row
        header = tk.Frame(card, bg=card_bg)
        header.pack(fill="x", padx=10, pady=(8, 2))

        # Icon + Name
        icon_name = f"{template.icon} {template.meta.name}" if template.icon else template.meta.name
        tk.Label(
            header, text=icon_name,
            font=("Segoe UI", 12, "bold"),
            bg=card_bg, fg=self.C.get("text", "#ffffff"),
        ).pack(side="left")

        # Version + Author
        tk.Label(
            header, text=f"v{template.meta.version} por {template.meta.author}",
            font=("Segoe UI", 9),
            bg=card_bg, fg=self.C.get("text_dim", "#a0a0a0"),
        ).pack(side="right")

        # Description
        desc = template.desc or template.meta.description
        if desc:
            tk.Label(
                card, text=desc,
                font=("Segoe UI", 9),
                bg=card_bg, fg=self.C.get("text_dim", "#a0a0a0"),
                wraplength=600, justify="left",
            ).pack(fill="x", padx=10, pady=(0, 4))

        # Tags
        if template.meta.tags:
            tags_frame = tk.Frame(card, bg=card_bg)
            tags_frame.pack(fill="x", padx=10, pady=(0, 4))

            for tag in template.meta.tags[:5]:
                tag_label = tk.Label(
                    tags_frame, text=f"#{tag}",
                    font=("Segoe UI", 8),
                    bg=self.C.get("button", "#0f3460"),
                    fg=self.C.get("text", "#ffffff"),
                    padx=6, pady=2,
                )
                tag_label.pack(side="left", padx=2)

        # Action buttons
        actions = tk.Frame(card, bg=card_bg)
        actions.pack(fill="x", padx=10, pady=(0, 8))

        # Enable/Disable toggle
        is_enabled = template.meta.is_enabled
        toggle_text = "🟢 Habilitado" if is_enabled else "🔴 Deshabilitado"
        toggle_cmd = lambda t=tid, e=is_enabled: self._toggle_plugin(t, not e)

        if CTK:
            toggle_btn = ctk.CTkButton(
                actions, text=toggle_text, command=toggle_cmd,
                width=120, height=26, font=("Segoe UI", 9),
                fg_color=self.C.get("success", "#00c853") if is_enabled else self.C.get("error", "#f44336"),
            )
        else:
            toggle_btn = tk.Button(
                actions, text=toggle_text, command=toggle_cmd,
                bg=self.C.get("success", "#00c853") if is_enabled else self.C.get("error", "#f44336"),
                fg=self.C.get("text", "#ffffff"),
                font=("Segoe UI", 9),
                relief="flat", padx=8, pady=2,
            )
        toggle_btn.pack(side="left", padx=3)

        # Export (for custom)
        if not template.meta.is_builtin:
            export_cmd = lambda t=tid: self._export_plugin(t)
            if CTK:
                export_btn = ctk.CTkButton(
                    actions, text="📤 Exportar", command=export_cmd,
                    width=100, height=26, font=("Segoe UI", 9),
                    fg_color=self.C.get("button", "#0f3460"),
                )
            else:
                export_btn = tk.Button(
                    actions, text="📤 Exportar", command=export_cmd,
                    bg=self.C.get("button", "#0f3460"),
                    fg=self.C.get("text", "#ffffff"),
                    font=("Segoe UI", 9),
                    relief="flat", padx=8, pady=2,
                )
            export_btn.pack(side="left", padx=3)

            # Delete
            delete_cmd = lambda t=tid: self._delete_plugin(t)
            if CTK:
                delete_btn = ctk.CTkButton(
                    actions, text="🗑️ Eliminar", command=delete_cmd,
                    width=100, height=26, font=("Segoe UI", 9),
                    fg_color=self.C.get("error", "#f44336"),
                )
            else:
                delete_btn = tk.Button(
                    actions, text="🗑️ Eliminar", command=delete_cmd,
                    bg=self.C.get("error", "#f44336"),
                    fg=self.C.get("text", "#ffffff"),
                    font=("Segoe UI", 9),
                    relief="flat", padx=8, pady=2,
                )
                delete_btn.pack(side="left", padx=3)

        # Info
        info_parts = []
        info_parts.append(f"max_tokens={template.max_tokens}")
        info_parts.append(f"temp={template.temperature}")
        info_parts.append(f"formato={template.output_format}")
        if template.language_hints:
            info_parts.append(f"idiomas={','.join(template.language_hints)}")

        tk.Label(
            actions, text=" | ".join(info_parts),
            font=("Segoe UI", 8),
            bg=card_bg, fg=self.C.get("text_dim", "#a0a0a0"),
        ).pack(side="right", padx=5)

    def _toggle_plugin(self, tid: str, enable: bool):
        """Habilita o deshabilita un plugin."""
        if enable:
            self.manager.enable_template(tid)
        else:
            self.manager.disable_template(tid)
        self._refresh_list()
        self.status_label.configure(text=f"Plugin {'habilitado' if enable else 'deshabilitado'}: {tid}")

    def _create_plugin(self):
        """Abre diálogo para crear un nuevo plugin."""
        CreatePluginDialog(self.parent, self.manager, self.C, on_create=self._refresh_list)

    def _install_plugin(self):
        """Instala un plugin desde un archivo."""
        filepath = filedialog.askopenfilename(
            title="Seleccionar plugin para instalar",
            filetypes=[
                ("Plugin JSON", "*.json"),
                ("Plugin Python", "*.py"),
                ("Todos los archivos", "*.*"),
            ],
        )

        if not filepath:
            return

        success, msg = self.manager.install_plugin(filepath)
        if success:
            messagebox.showinfo("Plugin instalado", msg)
            self._refresh_list()
            self.status_label.configure(text=msg)
        else:
            messagebox.showerror("Error", msg)

    def _export_plugin(self, tid: str):
        """Exporta un plugin a un archivo."""
        filepath = filedialog.asksaveasfilename(
            title="Exportar plugin",
            defaultextension=".json",
            filetypes=[("Plugin JSON", "*.json")],
            initialfile=f"{tid}.json",
        )

        if not filepath:
            return

        success, msg = self.manager.export_plugin(tid, filepath)
        if success:
            messagebox.showinfo("Plugin exportado", msg)
        else:
            messagebox.showerror("Error", msg)

    def _delete_plugin(self, tid: str):
        """Elimina un plugin personalizado."""
        if messagebox.askyesno("Confirmar", f"¿Eliminar plugin '{tid}'?"):
            success, msg = self.manager.uninstall_plugin(tid)
            if success:
                self._refresh_list()
                self.status_label.configure(text=msg)
            else:
                messagebox.showerror("Error", msg)

    def _open_plugins_dir(self):
        """Abre el directorio de plugins en el explorador."""
        import subprocess
        import platform

        custom_dir = self.manager.get_plugin_dirs()[1]  # plugins/custom/
        if platform.system() == "Windows":
            os.startfile(custom_dir)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", custom_dir])
        else:
            subprocess.Popen(["xdg-open", custom_dir])


class CreatePluginDialog:
    """Diálogo para crear un nuevo plugin."""

    def __init__(self, parent, manager: PluginManager, palette: dict, on_create: Optional[Callable] = None):
        self.parent = parent
        self.manager = manager
        self.C = palette
        self.on_create = on_create

        if CTK:
            self.dialog = ctk.CTkToplevel(parent)
        else:
            self.dialog = tk.Toplevel(parent)

        self.dialog.title("Crear Nuevo Plugin")
        self.dialog.geometry("500x500")
        self.dialog.resizable(False, False)
        self.dialog.configure(bg=self.C.get("bg", "#1a1a2e"))

        self._build_ui()
        self.dialog.transient(parent)
        self.dialog.grab_set()

    def _build_ui(self):
        """Construye el formulario de creación."""
        canvas = tk.Canvas(
            self.dialog, bg=self.C.get("bg", "#1a1a2e"),
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=self.C.get("bg", "#1a1a2e"))

        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Title
        tk.Label(
            form, text="📝 Nuevo Plugin de Template",
            font=("Segoe UI", 14, "bold"),
            bg=self.C.get("bg", "#1a1a2e"),
            fg=self.C.get("text", "#ffffff"),
        ).pack(pady=10)

        self.fields = {}
        field_defs = [
            ("id", "ID del Plugin *", "mi_plugin"),
            ("name", "Nombre *", "Mi Template"),
            ("description", "Descripción", "Descripción del template"),
            ("author", "Autor", "Tu nombre"),
            ("version", "Versión", "1.0.0"),
            ("icon", "Icono (emoji)", "📊"),
            ("max_tokens", "Max Tokens", "4096"),
            ("temperature", "Temperature", "0.3"),
        ]

        for field_name, label, default in field_defs:
            row = tk.Frame(form, bg=self.C.get("bg", "#1a1a2e"))
            row.pack(fill="x", padx=20, pady=3)

            tk.Label(
                row, text=label,
                font=("Segoe UI", 10),
                bg=self.C.get("bg", "#1a1a2e"),
                fg=self.C.get("text", "#ffffff"),
                width=15, anchor="w",
            ).pack(side="left")

            entry = tk.Entry(
                row,
                bg=self.C.get("card", "#16213e"),
                fg=self.C.get("text", "#ffffff"),
                font=("Segoe UI", 10),
                insertbackground=self.C.get("text", "#ffffff"),
            )
            entry.insert(0, default)
            entry.pack(side="right", fill="x", expand=True)
            self.fields[field_name] = entry

        # Prompt
        tk.Label(
            form, text="Prompt (requiere {TEXT}) *",
            font=("Segoe UI", 10, "bold"),
            bg=self.C.get("bg", "#1a1a2e"),
            fg=self.C.get("text", "#ffffff"),
        ).pack(anchor="w", padx=20, pady=(10, 3))

        self.prompt_text = tk.Text(
            form, height=10, width=50,
            bg=self.C.get("card", "#16213e"),
            fg=self.C.get("text", "#ffffff"),
            font=("Segoe UI", 10),
            insertbackground=self.C.get("text", "#ffffff"),
            wrap="word",
        )
        self.prompt_text.pack(fill="x", padx=20, pady=3)
        self.prompt_text.insert("1.0", "Analiza la siguiente transcripción...\n\nTranscripción:\n{TEXT}\n\nResultado:")

        # Tags
        tk.Label(
            form, text="Tags (separados por coma)",
            font=("Segoe UI", 10),
            bg=self.C.get("bg", "#1a1a2e"),
            fg=self.C.get("text", "#ffffff"),
        ).pack(anchor="w", padx=20, pady=(10, 3))

        self.tags_entry = tk.Entry(
            form,
            bg=self.C.get("card", "#16213e"),
            fg=self.C.get("text", "#ffffff"),
            font=("Segoe UI", 10),
            insertbackground=self.C.get("text", "#ffffff"),
        )
        self.tags_entry.pack(fill="x", padx=20, pady=3)
        self.tags_entry.insert(0, "custom, mi-template")

        # Buttons
        btn_frame = tk.Frame(form, bg=self.C.get("bg", "#1a1a2e"))
        btn_frame.pack(fill="x", padx=20, pady=15)

        if CTK:
            create_btn = ctk.CTkButton(
                btn_frame, text="✅ Crear Plugin", command=self._create,
                width=150, height=35, font=("Segoe UI", 11),
                fg_color=self.C.get("success", "#00c853"),
            )
        else:
            create_btn = tk.Button(
                btn_frame, text="✅ Crear Plugin", command=self._create,
                bg=self.C.get("success", "#00c853"),
                fg=self.C.get("text", "#ffffff"),
                font=("Segoe UI", 11),
                relief="flat", padx=20, pady=6,
            )
        create_btn.pack(side="left")

        if CTK:
            cancel_btn = ctk.CTkButton(
                btn_frame, text="Cancelar", command=self.dialog.destroy,
                width=100, height=35, font=("Segoe UI", 11),
                fg_color=self.C.get("button", "#0f3460"),
            )
        else:
            cancel_btn = tk.Button(
                btn_frame, text="Cancelar", command=self.dialog.destroy,
                bg=self.C.get("button", "#0f3460"),
                fg=self.C.get("text", "#ffffff"),
                font=("Segoe UI", 11),
                relief="flat", padx=20, pady=6,
            )
        cancel_btn.pack(side="left", padx=10)

    def _create(self):
        """Crea el plugin con los datos del formulario."""
        prompt = self.prompt_text.get("1.0", "end-1c").strip()

        if "{TEXT}" not in prompt:
            messagebox.showerror("Error", "El prompt debe contener {TEXT}")
            return

        tags_str = self.tags_entry.get().strip()
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        data = {
            "id": self.fields["id"].get().strip(),
            "name": self.fields["name"].get().strip(),
            "description": self.fields["description"].get().strip(),
            "author": self.fields["author"].get().strip(),
            "version": self.fields["version"].get().strip(),
            "icon": self.fields["icon"].get().strip(),
            "prompt": prompt,
            "tags": tags,
            "max_tokens": int(self.fields["max_tokens"].get().strip() or "4096"),
            "temperature": float(self.fields["temperature"].get().strip() or "0.3"),
        }

        if not data["id"] or not data["name"]:
            messagebox.showerror("Error", "ID y Nombre son requeridos")
            return

        success, msg = self.manager.create_plugin(data)
        if success:
            messagebox.showinfo("Plugin creado", msg)
            self.dialog.destroy()
            if self.on_create:
                self.on_create()
        else:
            messagebox.showerror("Error", msg)
