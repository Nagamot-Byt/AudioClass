#!/usr/bin/env python3
"""
theme.py — Sistema de diseno y temas de AudioClass
====================================================
Extraido de audioclass_v91.py para mantenibilidad.
Paletas WCAG AA, calculo de contraste, resolucion de fuentes.
"""

# ── Paletas WCAG AA ────────────────────────────────────────────────────────
# El acento es AZUL; fondos y superficies en escala de grises/azules pizarra;
# el ROJO queda reservado para GRABACION y acciones de peligro.
PALETTES = {
    "dark": {
        "bg": "#0F172A",
        "card": "#1E293B",
        "accent": "#60A5FA",
        "text": "#E2E8F0",
        "muted": "#94A3B8",
        "ok": "#22D3EE",
        "warn": "#F59E0B",
        "err": "#F07171",
        "border": "#64748B",
        "cloud": "#60A5FA",
        "gemini": "#60A5FA",
        "mic": "#F07171",
        "easy": "#22D3EE",
        "button": "#334155",
        "academic": "#60A5FA",
        "header": "#0F172A",
        "head_text": "#E2E8F0",
        "accent_hover": "#3B82F6",
    },
    "light": {
        "bg": "#F1F5F9",
        "card": "#FFFFFF",
        "accent": "#2563EB",
        "text": "#000000",
        "muted": "#475569",
        "ok": "#0F766E",
        "warn": "#92400E",
        "err": "#B91C1C",
        "border": "#7C8CA0",
        "cloud": "#1D4ED8",
        "gemini": "#2563EB",
        "mic": "#B91C1C",
        "easy": "#0F766E",
        "button": "#E2E8F0",
        "academic": "#2563EB",
        "header": "#1E293B",
        "head_text": "#F1F5F9",
        "accent_hover": "#1D4ED8",
    },
}


def relative_luminance(hexc):
    """Luminancia relativa WCAG de un color hex."""
    hexc = str(hexc).lstrip("#")
    vals = [int(hexc[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(vals[0]) + 0.7152 * lin(vals[1]) + 0.0722 * lin(vals[2])


def btn_text_color(bg):
    """Texto de boton con el MAYOR contraste WCAG posible sobre el fondo dado:
    negro o blanco, el que gane."""
    try:
        l = relative_luminance(bg)
        c_black = (l + 0.05) / 0.05
        c_white = 1.05 / (l + 0.05)
        return "#000000" if c_black >= c_white else "#FFFFFF"
    except Exception:
        return "#FFFFFF"


def resolve_fonts():
    """Resuelve fuentes del sistema (head, body, mono) disponibles."""
    import tkinter.font as tkfont

    try:
        fams = set(tkfont.families())
    except Exception:
        fams = set()
    head = next(
        (f for f in ("Merriweather", "Georgia", "Cambria", "Times New Roman") if f in fams),
        "Segoe UI",
    )
    body = next((f for f in ("Inter", "Segoe UI", "Tahoma") if f in fams), "Segoe UI")
    mono = next(
        (f for f in ("Source Code Pro", "Consolas", "Courier New") if f in fams),
        "Consolas",
    )
    return head, body, mono


def load_bundled_fonts():
    """Registra las fuentes DejaVu empaquetadas (assets/) para Tk/CTk."""
    import os
    import tkinter.font as tkfont

    assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    for fn in os.listdir(assets) if os.path.isdir(assets) else []:
        if fn.lower().endswith(".ttf"):
            try:
                path = os.path.join(assets, fn)
                tkfont.Font(file=path)
            except Exception:
                pass


# ── Detección automática de tema del sistema ─────────────────────────────────
_system_theme_listener = None


def detect_system_theme() -> str:
    """Detecta el tema del sistema operativo (dark/light).

    Returns:
        'dark' o 'light'
    """
    try:
        import darkdetect

        theme = darkdetect.theme()
        if theme:
            return theme.lower()  # 'Dark' -> 'dark', 'Light' -> 'light'
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: intentar detectar manualmente
    try:
        import platform
        import subprocess

        system = platform.system()

        if system == "Darwin":
            # macOS: usar defaults
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=5
            )
            return "dark" if "Dark" in result.stdout else "light"

        elif system == "Linux":
            # Linux: verificar GTK theme o variable de entorno
            import os

            gtk_theme = os.environ.get("GTK_THEME", "")
            if "dark" in gtk_theme.lower():
                return "dark"

            # Verificar freedesktop portal
            try:
                result = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "dark" in result.stdout.lower():
                    return "dark"
            except Exception:
                pass

        elif system == "Windows":
            # Windows: verificar registro
            try:
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                return "light" if value == 1 else "dark"
            except Exception:
                pass

    except Exception:
        pass

    return "dark"  # Default


def start_theme_watcher(callback, interval_ms: int = 5000):
    """Inicia un watcher que detecta cambios de tema del sistema.

    Args:
        callback: Función a llamar cuando cambia el tema (recibe 'dark' o 'light').
        interval_ms: Intervalo de verificación en milisegundos.
    """
    global _system_theme_listener

    # Usar darkdetect listener si está disponible
    try:
        import darkdetect

        def _on_theme_change(theme):
            if theme:
                callback(theme.lower())

        _system_theme_listener = darkdetect.Listener(_on_theme_change)
        _system_theme_listener.start()
        return
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: polling cada N segundos
    import threading

    last_theme = [detect_system_theme()]

    def _poll():
        while True:
            try:
                current = detect_system_theme()
                if current != last_theme[0]:
                    last_theme[0] = current
                    callback(current)
            except Exception:
                pass

            import time

            time.sleep(interval_ms / 1000.0)

    _system_theme_listener = threading.Thread(target=_poll, daemon=True)
    _system_theme_listener.start()


def stop_theme_watcher():
    """Detiene el watcher de cambios de tema."""
    global _system_theme_listener

    if _system_theme_listener is not None:
        try:
            if hasattr(_system_theme_listener, "stop"):
                _system_theme_listener.stop()
        except Exception:
            pass
        _system_theme_listener = None
