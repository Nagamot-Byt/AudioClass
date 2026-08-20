# -*- coding: utf-8 -*-
"""export_utils.py — Funciones auxiliares de exportacion PDF y DOCX.

Modulo extraido de audioclass_v91.py para reducir el tamano del monolito.
Contiene las funciones puras de generacion de documentos que no dependen
del estado de la clase App (solo reciben datos como argumentos).

Uso:
    from export_utils import fmt_timestamp, export_lines, docx_paragraph

Estas funciones son deterministas y testables sin instanciar la GUI.
"""
import re
from datetime import datetime


# ── Timestamps ─────────────────────────────────────────────────────────────

def fmt_timestamp(sec):
    """Convierte segundos a formato mm:ss para timestamps de exportacion.

    Args:
        sec: Segundos (int o float). None o 0 devuelven '00:00'.

    Returns:
        str en formato 'mm:ss'.

    Examples:
        >>> fmt_timestamp(0)
        '00:00'
        >>> fmt_timestamp(125)
        '02:05'
        >>> fmt_timestamp(None)
        '00:00'
    """
    sec = int(sec or 0)
    m, s = divmod(sec, 60)
    return f"{m:02d}:{s:02d}"


# ── Lineas de exportacion ─────────────────────────────────────────────────

def export_lines(last_text, last_segments=None, max_len=90):
    """Devuelve (has_timestamps, lines) para exportar transcripcion.

    Si hay segmentos (transcripcion 'Con tiempos') cada linea lleva
    [mm:ss - mm:ss]; si no, el texto se parte en lineas numeradas.

    Args:
        last_text: Texto completo de la transcripcion.
        last_segments: Lista de dicts con 'start', 'end', 'text'.
        max_len: Longitud maxima de linea (para wrap sin timestamps).

    Returns:
        Tupla (has_ts, lines) donde:
        - has_ts: bool, True si las lineas tienen timestamps
        - lines: list de tuplas (start, end, text) o (None, None, text)
    """
    segs = last_segments or []
    lines = []
    if segs:
        for s in segs:
            txt = str(s.get("text", "") or "").strip()
            if txt:
                lines.append((s.get("start", 0), s.get("end", 0), txt))
        if lines:
            return True, lines

    # Sin timestamps: partir el texto en lineas numeradas
    t = (last_text or "").replace("\r", "").strip()
    for para in t.split("\n"):
        para = para.strip()
        if not para:
            continue
        while len(para) > max_len:
            cut = para.rfind(" ", 0, max_len)
            if cut < 20:
                cut = max_len
            lines.append((None, None, para[:cut]))
            para = para[cut:].strip()
        if para:
            lines.append((None, None, para))
    if not lines:
        lines = [(None, None, t)]
    return False, lines


# ── DOCX helpers ──────────────────────────────────────────────────────────

def docx_paragraph(text, bold=False, size=22, color=None, shading=None,
                   center=False, mono=False):
    """Genera un parrafo WordprocessingML a partir de texto plano.

    El orden de los hijos de w:pPr debe seguir la secuencia del esquema
    OOXML (CT_PPr): w:shd va ANTES de w:spacing y w:jc; si no, Word puede
    marcar el archivo como corrupto o ignorar el sombreado.

    Args:
        text: Texto del parrafo.
        bold: Negrita.
        size: Tamano de fuente en half-points (22 = 11pt).
        color: Color en hex (ej: '0A1F44').
        shading: Color de fondo en hex.
        center: Centrar el texto.
        mono: Fuente monoespaciada (Consolas).

    Returns:
        str con XML WordprocessingML del parrafo.
    """
    from xml.sax.saxutils import escape
    rpr = ""
    if bold:
        rpr += "<w:b/>"
    if color:
        rpr += f'<w:color w:val="{color}"/>'
    if mono:
        rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>'
    rpr += f'<w:sz w:val="{size}"/>'
    ppr = ""
    if shading:
        ppr += f'<w:shd w:val="clear" w:color="auto" w:fill="{shading}"/>'
    ppr += '<w:spacing w:after="60"/>' if not mono else '<w:spacing w:line="240" w:lineRule="auto"/>'
    if center:
        ppr += '<w:jc w:val="center"/>'
    return ('<w:p><w:pPr>' + ppr + '</w:pPr><w:r><w:rPr>' + rpr +
            '</w:rPr><w:t xml:space="preserve">' + escape(text) + '</w:t></w:r></w:p>')


def docx_heading(text, size=24):
    """Encabezado de seccion del informe (negrita, azul marino academico).

    Args:
        text: Texto del encabezado.
        size: Tamano de fuente en half-points.

    Returns:
        str con XML WordprocessingML del encabezado.
    """
    return docx_paragraph(text, bold=True, size=size, color="0A1F44")


# ── PDF helpers ───────────────────────────────────────────────────────────

_PDF_FALLBACK_CHARS = {
    "\u2013": "-",   # en-dash
    "\u2014": "--",  # em-dash
    "\u2018": "'",   # left single quote
    "\u2019": "'",   # right single quote
    "\u201c": '"',   # left double quote
    "\u201d": '"',   # right double quote
    "\u2026": "...",  # ellipsis
    "\u2022": "*",   # bullet
    "\u00e9": "e",   # e-acute
    "\u00e1": "a",   # a-acute
    "\u00ed": "i",   # i-acute
    "\u00f3": "o",   # o-acute
    "\u00fa": "u",   # u-acute
    "\u00f1": "n",   # n-tilde
    "\u00fc": "u",   # u-diaeresis
}


def pdf_safe_latin1(text):
    """Convierte simbolos tipograficos a ASCII para fuentes latin-1.

    Args:
        text: Texto con posibles simbolos Unicode.

    Returns:
        str seguro para fuentes latin-1.
    """
    for k, v in _PDF_FALLBACK_CHARS.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def pdf_badge(pdf, fam, tit_style, full_unicode):
    """Dibuja insignia verde '[OK] Revisado por IA' en el PDF.

    Args:
        pdf: Instancia FPDF.
        fam: Nombre de familia de fuente.
        tit_style: Estilo de titulo ('B' o '').
        full_unicode: Si la fuente soporta Unicode completo.
    """
    try:
        label = "Revisado por IA" if full_unicode else "Revisado por IA"
        pdf.set_font(fam, tit_style, 10)
        bw = pdf.get_string_width(label) + 12
        bx = (210 - bw) / 2
        by = pdf.get_y()
        pdf.set_fill_color(59, 130, 246)  # azul acento
        try:
            pdf.rect(bx, by, bw, 8, style="F", round_corners=True, corner_radius=4)
        except Exception:
            pdf.rect(bx, by, bw, 8, style="F")
        pdf.set_xy(bx, by + 1)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(bw, 6, label, align="C")
        pdf.set_xy(10, by + 10)
        pdf.set_text_color(30, 30, 30)
    except Exception:
        pass


# ── Adaptacion academica ──────────────────────────────────────────────────

def parse_adapt_sections(text):
    """Parsea la adaptacion academica de Gemini en secciones.

    Soporta dos formatos: encabezado en su propia linea con el cuerpo
    debajo, o encabezado INLINE ("**Resumen Ejecutivo:** texto").
    Si no encuentra encabezados conocidos, devuelve una sola seccion.

    Args:
        text: Texto de la adaptacion academica.

    Returns:
        Lista de tuplas (nombre_seccion, contenido).
    """
    text = text.replace("\r", "")
    HEADERS = [
        ("Resumen Ejecutivo", r"resumen\s+ejecutivo"),
        ("Tesis Central", r"tesis\s+central"),
        ("Pilares Argumentales", r"pilares\s+argumentales"),
        ("Evidencia y Datos Duros", r"evidencia\s+y\s+datos\s+duros"),
        ("Implicacion o Aplicabilidad", r"implicaci[oó]n\s+o\s+aplicabilidad"),
        ("Implicacion", r"implicaci[oó]n"),
        ("Registro de Filtrado", r"registro\s+de\s+filtrado"),
    ]
    lines = text.split("\n")
    hits = []
    for i, ln in enumerate(lines):
        norm = re.sub(r"^[\s\d.\-:()*#•]+", "", ln).strip(" *#\t")
        norm = re.sub(r"\s+", " ", norm).lower()
        for label, pat in HEADERS:
            if re.match(pat, norm):
                if not hits or hits[-1][2] != i:
                    hits.append((label, pat, i))
                break
    if not hits:
        return [("Analisis Academico", text.strip())]
    sections = []
    for k, (label, pat, idx) in enumerate(hits):
        end = hits[k + 1][2] if k + 1 < len(hits) else len(lines)
        raw = lines[idx]
        stripped = re.sub(r"^[\s\d.\-:()*#•]+", "", raw).strip()
        m = re.search(pat, stripped, flags=re.IGNORECASE)
        inline = ""
        if m:
            inline = re.sub(r"^[.:*\-#•]+", "", stripped[m.end():]).strip()
        body_lines = [x.strip() for x in lines[idx + 1:end] if x.strip()]
        body = "\n".join(filter(None, [inline] + body_lines)).strip()
        sections.append((label, body))
    return sections
