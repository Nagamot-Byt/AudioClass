"""Test de exportacion PDF/DOCX: genera archivos reales con timestamps,
numeracion de lineas e insignia 'Revisado por IA' y verifica su contenido."""
import os, sys, zipfile, tempfile, traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# La consola de Windows (cp1252) no imprime '✓' ni emojis: reconfigure a utf-8
# para que los prints del test no lancen UnicodeEncodeError sin PYTHONIOENCODING.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import audioclass_v91 as appmod

# ── Simular el App sin abrir dialogo de guardado ─────────────────────────────
_saved = {}

def fake_save(**kw):
    def _f(**kwargs):
        p = os.path.join(tempfile.mkdtemp(), kwargs.get("initialfile", "out.pdf"))
        _saved[kwargs.get("defaultextension", ".pdf")] = p
        return p
    return _f

appmod.filedialog.asksaveasfilename = fake_save()

try:
    import customtkinter as ctk
except ImportError:
    ctk = None

# Instanciar la app (sin mainloop); neutralizar dialogs modales que
# bloquearian el test (messagebox en _msg espera clic del usuario).
app = appmod.App()
app._msg = lambda kind, title, msg: print(f"MSGBOX [{kind}] {title}: {msg}")
# En el informe DOCX pedimos 'incluir informe' -> True; para el resto False
_ask_calls = []
def fake_ask(*a, **k):
    _ask_calls.append(a[1] if len(a) > 1 else "")
    return True
app._ask = fake_ask
app.last_text = ("Hola. Esta es una prueba de transcripción. El proceso ocurre en "
                 "los cloroplastos y produce glucosa y oxígeno. " * 3)
app.last_segments = [
    {"start": 0.0, "end": 5.2, "text": "Hola, esta es una prueba de transcripción."},
    {"start": 5.2, "end": 12.8, "text": "El proceso ocurre en los cloroplastos."},
    {"start": 12.8, "end": 30.1, "text": "Produce glucosa y oxígeno."},
]
app.last_model = "tiny"
app.last_path = "clase_20260101_100000_mejorado.wav"

# Simular una adaptacion de Gemini (formato del ACADEMIC_PROMPT)
adapt_txt = (
    "**Resumen Ejecutivo:** La clase explica la fotosíntesis: el proceso ocurre en los cloroplastos "
    "y produce glucosa y oxígeno.\n\n"
    "**Tesis Central:** La fotosíntesis es el proceso bioquímico que sostiene la vida en la Tierra.\n\n"
    "**Pilares Argumentales:**\n"
    "1. Ocurre en los cloroplastos.\n"
    "2. Produce glucosa y oxígeno.\n"
    "3. Requiere luz solar.\n\n"
    "**Evidencia y Datos Duros:** 6 moléculas de CO2 + 6 de agua producen glucosa.\n\n"
    "**Implicación o Aplicabilidad:** Se aplica en agricultura y biotecnología.\n\n"
    "**Registro de Filtrado:** Murmullos y preguntas sin respuesta descartados."
)
try:
    app.adapt_txt.configure(state="normal")
    app.adapt_txt.delete("1.0", "end")
    app.adapt_txt.insert("end", f"🎓 Análisis Académico Profundo\n{'='*55}\n\n{adapt_txt}\n")
    app.adapt_txt.configure(state="disabled")
except Exception as e:
    print("WARN adapt_txt:", e)

# Parser de secciones de la adaptacion
sections = app._parse_adapt_sections(adapt_txt)
print("SECCIONES:", [s[0] for s in sections])
for lbl, body in sections:
    print(("OK  " if body.strip() else "FAIL") + " seccion: " + lbl)

# ── 1) PDF ──────────────────────────────────────────────────────────────────
app._pdf()
pdf_path = _saved.get(".pdf")
print("PDF:", pdf_path, os.path.getsize(pdf_path) if pdf_path else "NO")
if not pdf_path or not os.path.exists(pdf_path):
    print("PDF_FAIL"); sys.exit(1)

from pypdf import PdfReader
reader = PdfReader(pdf_path)
txt = "\n".join(p.extract_text() or "" for p in reader.pages)
print("=== PDF TEXT ===")
print(txt[:600])
checks = {
    "PDF insignia": "Revisado por IA" in txt,
    "PDF timestamp": "[00:05 - 00:12]" in txt,
    "PDF numeracion": "[  2]" in txt or "[2]" in txt,
    "PDF modelo": "Modelo: tiny" in txt,
}
for k, v in checks.items():
    print(("OK " if v else "FAIL ") + k)

# ── 2) DOCX ─────────────────────────────────────────────────────────────────
app._export_docx()
docx_path = _saved.get(".docx")
print("DOCX:", docx_path, os.path.getsize(docx_path) if docx_path else "NO")
if not docx_path or not os.path.exists(docx_path):
    print("DOCX_FAIL"); sys.exit(1)

with zipfile.ZipFile(docx_path) as z:
    names = z.namelist()
    doc_xml = z.read("word/document.xml").decode("utf-8")
    ct = z.read("[Content_Types].xml").decode("utf-8")
    rels = z.read("_rels/.rels").decode("utf-8")
print("DOCX parts:", names)
c_checks = {
    "DOCX insignia": "Revisado por IA" in doc_xml,
    "DOCX timestamp": "[00:05 - 00:12]" in doc_xml,
    "DOCX numeracion": "[  2]" in doc_xml or "[2]" in doc_xml,
    "DOCX modelo": "Modelo: tiny" in doc_xml,
    "DOCX shd verde": 'w:fill="10B981"' in doc_xml,
    "DOCX content-types": "wordprocessingml.document.main+xml" in ct,
    "DOCX rels": "word/document.xml" in rels,
    # Informe academico
    "DOCX informe titulo": "Informe Académico (Gemini)" in doc_xml,
    "DOCX resumen": "Resumen Ejecutivo" in doc_xml,
    "DOCX tesis": "Tesis Central" in doc_xml,
    "DOCX pilares": "Pilares Argumentales" in doc_xml,
    "DOCX evidencia": "Evidencia y Datos Duros" in doc_xml,
    "DOCX implicacion": "Implicación o Aplicabilidad" in doc_xml,
    "DOCX registro filtrado": "Registro de Filtrado" in doc_xml,
    "DOCX transcripcion completa": "Transcripción Completa" in doc_xml,
    "DOCX contenido informe": "La fotosíntesis es el proceso bioquímico" in doc_xml,
}
for k, v in c_checks.items():
    print(("OK " if v else "FAIL ") + k)

all_ok = all(checks.values()) and all(c_checks.values()) and len(sections) >= 6
print("EXPORT_OK" if all_ok else "EXPORT_FAIL")
# Limpiar
import tkinter as tk
try:
    app.destroy()
    app.update_idletasks()
except Exception:
    pass
try:
    # Cerrar la ventana raiz para que el proceso termine
    roots = [w for w in tk._default_root and [tk._default_root] or []]
    for r in roots:
        try:
            r.destroy()
        except Exception:
            pass
except Exception:
    pass
sys.exit(0 if all_ok else 1)
