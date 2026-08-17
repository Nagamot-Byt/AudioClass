#!/usr/bin/env bash
# -*- coding: utf-8 -*-
# ═══════════════════════════════════════════════════════════════════════════
#  desplegar_produccion.sh — DESPLIEGUE DE PRODUCCIÓN de AudioClass (1 comando)
#
#  Recompila el exe onefile con PyInstaller, copia los entregables (raíz + zip)
#  y ejecuta TODA la validación de producción. Falla (exit != 0) si algo no
#  cumple, y escribe un log completo en despliegue.log.
#
#  USO (Git Bash en Windows):
#    ./desplegar_produccion.sh               # todo: build + entregables + validación
#    ./desplegar_produccion.sh --skip-build  # usa el exe ya compilado (solo validar)
#    ./desplegar_produccion.sh --skip-benchmark   # omite el benchmark de modelos (lento)
#    ./desplegar_produccion.sh --quick       # build + copiar + selftest (validación mínima)
#    ./desplegar_produccion.sh --with-onedir  # ademas: build onedir (carpeta, arranque rapido) + zip
#    ./desplegar_produccion.sh --help
#
#  Fases:
#    [0] Preflight        python + pyinstaller + assets + specs
#    [1] Tests del fuente suite ÚNICA run_ci_suite.py (13 tests: UI, privacidad,
#                        WCAG, Colab, motor, exportación, E2E, estrés, v10,
#                        lang_auto, watchdog, benchmark) — la misma que el CI
#    [2] Build onefile    PyInstaller AudioClass_v91_onefile.spec -> dist_onefile/
#    [3] Entregables      copia a "AudioClass COMPLETA v9.1.exe" + regenera el zip
#    [4] Exe: selftest    --selftest-transcribe tts_clase.wav (texto real, 100%)
#    [4b] Exe: E2E UI     --e2e-ui wizard|config|widgets (flujos reales de la interfaz, headless)
#    [5] Exe: WCAG + diálogo micrófono débil  run_wcag_on_exe.py + test_mic_warn_on_exe.py
#                        (contraste y diálogo de advertencia sobre el código empaquetado)
#    [6] Integridad zip   SHA-256 del exe dentro del zip == entregable raíz
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

# ── Configuración ────────────────────────────────────────────────────────────
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

LOG="despliegue.log"
SPEC="AudioClass_v91_onefile.spec"
EXE_SRC="dist_onefile/AudioClass.exe"
EXE_DEST="AudioClass COMPLETA v9.1.exe"
ZIP_DEST="AudioClass_v9.1_COMPLETA.zip"
AUDIO_TEST="tts_clase.wav"
OUT_SELFTEST="selftest_result.txt"
PROG_SELFTEST="selftest_progress.txt"

DO_BUILD=1
DO_BENCHMARK=1
DO_FULL_VALIDATION=1
DO_ONEDIR=0

for arg in "$@"; do
    case "$arg" in
        --skip-build) DO_BUILD=0 ;;
        --skip-benchmark) DO_BENCHMARK=0 ;;
        --with-onedir) DO_ONEDIR=1 ;;
        --quick) DO_BENCHMARK=0 ;;
        --help|-h)
            sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "Argumento desconocido: $arg  (usa --help)"; exit 1 ;;
    esac
done

# ── Colores ──────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'; C_BLU=$'\033[36m'; C_BLD=$'\033[1m'; C_END=$'\033[0m'
else
    C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_BLD=""; C_END=""
fi

PASS=0; FAIL=0; WARN=0

# Timeouts por fase (los tests Tk son flaky: a veces la creacion de raices
# extra del wizard se queda colgada; un timeout por test lo hace robusto).
TIMEOUT_TEST=300      # tests de UI/WCAG/transcripcion
TIMEOUT_SELFTEST=360  # selftest del exe (onefile descomprime ~60-90s + transcripcion)
TIMEOUT_WCAG_EXE=480  # run_wcag_on_exe (crea varias instancias de la app)

log() { printf '%s\n' "$*" | tee -a "$LOG"; }
ok()  { log "${C_GRN}[OK]${C_END} $*"; PASS=$((PASS+1)); }
warn(){ log "${C_YEL}$*${C_END}"; WARN=$((WARN+1)); }
fail(){ log "${C_RED}$*${C_END}"; FAIL=$((FAIL+1)); }
step(){ log ""; log "${C_BLU}════════ $* ( $(date '+%H:%M:%S') ) ════════${C_END}"; }

# Ejecuta un comando con timeout (Git Bash puede no tener 'timeout'):
#   run_limited <segundos> <comando...>
run_limited() {
    local limit="$1"; shift
    "$@" >/tmp/_deploy_out.txt 2>&1 &
    local pid=$! waited=0
    while kill -0 "$pid" 2>/dev/null && [ "$waited" -lt "$limit" ]; do
        sleep 5; waited=$((waited + 5))
    done
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null
        return 124   # timeout
    fi
    wait "$pid"
    return $?
}

# ── Python ───────────────────────────────────────────────────────────────────
find_python() {
    local cands=()
    [ -n "${LOCALAPPDATA:-}" ] && cands+=("$LOCALAPPDATA/Programs/Python/Python312/python.exe")
    cands+=("$LOCALAPPDATA/Programs/Python/Python311/python.exe")
    for c in "${cands[@]}"; do
        [ -x "$c" ] && { PY="$c"; return 0; }
    done
    if command -v py >/dev/null 2>&1; then
        PY="$(py -3 -c "import sys; print(sys.executable)" 2>/dev/null)" && [ -n "$PY" ] && return 0
    fi
    if command -v python >/dev/null 2>&1; then
        PY="$(python -c "import sys; print(sys.executable)" 2>/dev/null)" && [ -n "$PY" ] && return 0
    fi
    return 1
}

run_tests() {
    # $1 = test (sin .py), $2 = patrón de éxito. Con timeout por test.
    local name="$1"; shift
    local okpat="$1"; shift
    local t0 t1 out rc
    t0=$(date +%s)
    run_limited "$TIMEOUT_TEST" "$PY" -u "$name.py"
    rc=$?
    t1=$(date +%s)
    out=$(cat /tmp/_deploy_out.txt 2>/dev/null); rm -f /tmp/_deploy_out.txt
    if [ "$rc" -eq 124 ]; then
        fail "$name (timeout >${TIMEOUT_TEST}s)"
        return
    fi
    if [ "$rc" -eq 0 ] && printf '%s' "$out" | grep -qE "$okpat"; then
        ok "$name en $((t1 - t0))s ($(printf '%s' "$out" | grep -oE "$okpat" | head -1 | tr -d '\r'))"
    else
        fail "$name (rc=$rc)"
        printf '%s\n' "$out" | tail -8 | sed 's/^/      /' | tee -a "$LOG"
    fi
}

# ════════════════════════════════════════════════════════════════════════════
echo "" > "$LOG"
log "${C_BLD} DESPLIEGUE DE PRODUCCIÓN — AudioClass v9.1${C_END}"
log "   $(date '+%Y-%m-%d %H:%M:%S')   (log: $LOG)"
[ "$DO_BUILD" = 1 ] && log "   Modo: build + entregables + validación completa"
[ "$DO_BUILD" = 0 ] && log "   Modo: validación (--skip-build: usa el exe ya compilado)"
[ "$DO_BENCHMARK" = 0 ] && log "   Benchmark de modelos: OMITIDO"

# ── [0] PREFLIGHT ────────────────────────────────────────────────────────────
step "[0] Preflight"
if find_python; then
    ok "Python: $PY"
else
    fail "Python no encontrado (busca Python 3.11/3.12 en %LOCALAPPDATA%\\Programs\\Python)"
    echo; log "RESULTADO: FALLA — $FAIL fallo(s)"
    exit 1
fi
"$PY" -c "import PyInstaller" >/dev/null 2>&1 && ok "PyInstaller instalado" || { fail "PyInstaller no instalado (pip install pyinstaller)"; }
for f in "$SPEC" "assets/audioclass_theme.json" "models/tiny.pt" "models_ct2/tiny/model.bin" "models_ct2/base/model.bin" "$AUDIO_TEST"; do
    [ -f "$f" ] && ok "asset presente: $f" || { fail "falta asset: $f"; }
done
AUDIO_DUR=$("$PY" -c "from scipy.io import wavfile; sr,d=wavfile.read(r'$AUDIO_TEST'); print(f'{len(d)/sr:.0f}')" 2>/dev/null || echo '?')
log "  Audio de prueba: $AUDIO_TEST (${AUDIO_DUR}s)"

# ── [1] TESTS DEL FUENTE (suite ÚNICA compartida con el CI) ──────────────────
# run_ci_suite.py es la ÚNICA fuente de verdad de la suite: los 13 tests
# (UI smoke/v91, WCAG, privacidad, seguridad Colab, motor paralelo,
# exportación, E2E de UI, estrés, v10, lang_auto, watchdog y benchmark).
# ci.yml la consume igual -> CI y despliegue no pueden divergir.
# Los tests GUI se envuelven con xvfb-run SOLO en Linux sin DISPLAY;
# en Windows el display es nativo y no hace falta.
step "[1] Tests del código fuente (run_ci_suite.py)"
if "$PY" -m py_compile audioclass_v91.py audioclass_core.py run_ci_suite.py 2>/dev/null; then ok "py_compile (PY_OK)"; else fail "py_compile"; fi
SUITE_ARGS=()
[ "$DO_BENCHMARK" = 0 ] && SUITE_ARGS+=(--skip-benchmark)
T0=$(date +%s)
run_limited 1500 "$PY" -u run_ci_suite.py "${SUITE_ARGS[@]}"
RC=$?
T1=$(date +%s)
out=$(cat /tmp/_deploy_out.txt 2>/dev/null); rm -f /tmp/_deploy_out.txt
if [ "$RC" -eq 0 ] && printf '%s' "$out" | grep -q "CI_SUITE_OK"; then
    ok "suite del fuente en $((T1 - T0))s ($(printf '%s' "$out" | grep -oE 'CI_SUITE_OK \([^)]*\)' | head -1 | tr -d '\r'))"
else
    fail "suite del fuente (rc=$RC)"
    printf '%s\n' "$out" | grep -E "FAIL|Error|Traceback" | sed 's/^/      /' | tail -10 | tee -a "$LOG"
fi

if [ "$FAIL" -gt 0 ]; then
    log ""
    log "${C_RED}FALLARON tests del fuente — no se compila ni despliega.${C_END}"
    log "RESULTADO: FALLA — $FAIL fallo(s)"
    exit 1
fi

# ── [2] BUILD ONEFILE ────────────────────────────────────────────────────────
if [ "$DO_BUILD" = 1 ]; then
    step "[2] Build onefile (PyInstaller — puede tardar 8-20 min)"
    log "  Ejecutando: $PY -m PyInstaller --noconfirm --distpath dist_onefile $SPEC"
    T0=$(date +%s)
    if "$PY" -m PyInstaller --noconfirm --distpath dist_onefile "$SPEC" >> "$LOG" 2>&1; then
        T1=$(date +%s)
        ok "Build completado en $(( (T1 - T0) / 60 ))m $(( (T1 - T0) % 60 ))s"
    else
        fail "Build PyInstaller falló (revisa el final de $LOG)"
        tail -20 "$LOG" | sed 's/^/      /'
        log "RESULTADO: FALLA — $FAIL fallo(s)"
        exit 1
    fi
    [ -f "$EXE_SRC" ] && ok "Exe generado: $EXE_SRC ($(stat -c%s "$EXE_SRC") bytes)" || fail "No se generó $EXE_SRC"
else
    step "[2] Build (--skip-build)"
    [ -f "$EXE_SRC" ] && ok "Se usa el exe existente: $EXE_SRC" || fail "No existe $EXE_SRC (quita --skip-build)"
fi

# ── [3] ENTREGABLES ──────────────────────────────────────────────────────────
step "[3] Entregables (raíz + zip)"
if [ -f "$EXE_SRC" ]; then
    cp -f "$EXE_SRC" "$EXE_DEST" && ok "Copiado a $EXE_DEST ($(stat -c%s "$EXE_DEST") bytes)"
    # El LEEME viaja dentro del zip: instrucciones de SmartScreen, primera
    # apertura y microfono para el usuario final.
    "$PY" -c "
import zipfile, os
with zipfile.ZipFile(r'$ZIP_DEST', 'w', zipfile.ZIP_DEFLATED) as z:
    z.write(r'$EXE_DEST', r'$EXE_DEST')
    for doc in ('LEEME.txt', 'EULA.txt', 'AVISO_DE_PRIVACIDAD.txt', 'TERCEROS_Y_LICENCIAS.md'):
        if os.path.exists(doc):
            z.write(doc)
print('zip ok')
" >> "$LOG" 2>&1 && ok "Zip regenerado: $ZIP_DEST ($(stat -c%s "$ZIP_DEST") bytes)" || fail "No se pudo regenerar el zip"
else
    fail "Sin exe no se pueden copiar entregables"
fi

# ── [3b] ONEDIR (alternativa de arranque rapido) ─────────────────────────────
if [ "$DO_ONEDIR" = 1 ]; then
    step "[3b] Build onedir (carpeta, arranque rapido) + selftest + zip"
    T0=$(date +%s)
    if "$PY" -m PyInstaller --noconfirm AudioClass_v91.spec >> "$LOG" 2>&1; then
        T1=$(date +%s)
        ok "Onedir build en $(( (T1 - T0) / 60 ))m $(( (T1 - T0) % 60 ))s"
    else
        fail "Build onedir fallo (revisa el final de $LOG)"
        tail -20 "$LOG" | sed 's/^/      /'
    fi
    EXE_ONEDIR="dist/AudioClass/AudioClass.exe"
    if [ -f "$EXE_ONEDIR" ]; then
        ok "Onedir generado: $EXE_ONEDIR ($(stat -c%s "$EXE_ONEDIR") bytes)"
        rm -f "$OUT_SELFTEST" "$PROG_SELFTEST"
        T0=$(date +%s)
        run_limited "$TIMEOUT_SELFTEST" ./"$EXE_ONEDIR" --selftest-transcribe "$AUDIO_TEST" "$OUT_SELFTEST" "$PROG_SELFTEST"
        RC=$?
        T1=$(date +%s)
        if [ "$RC" -eq 0 ] && [ -s "$OUT_SELFTEST" ] && grep -q "100%" "$PROG_SELFTEST"; then
            ok "selftest onedir exit=0 ($((T1 - T0))s, texto + 100%)"
        else
            fail "selftest onedir (rc=$RC)"
        fi
        rm -f "$OUT_SELFTEST" "$PROG_SELFTEST"
        ZIP_ONEDIR="AudioClass_v9.1_ONEDIR.zip"
        "$PY" -c "
import zipfile, os
with zipfile.ZipFile(r'$ZIP_ONEDIR', 'w', zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk('dist/AudioClass'):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, 'dist'))
    for doc in ('LEEME.txt', 'EULA.txt', 'AVISO_DE_PRIVACIDAD.txt', 'TERCEROS_Y_LICENCIAS.md'):
        if os.path.exists(doc):
            z.write(doc)
print('zip onedir ok')
" >> "$LOG" 2>&1 && ok "Zip onedir: $ZIP_ONEDIR ($(stat -c%s "$ZIP_ONEDIR") bytes)" \
        || fail "No se pudo crear el zip onedir"
    else
        fail "No se genero $EXE_ONEDIR"
    fi
fi

# ── [4] SELFTEST DEL EXE ─────────────────────────────────────────────────────
step "[4] Validación del exe: --selftest-transcribe"
if [ -f "$EXE_SRC" ]; then
    rm -f "$OUT_SELFTEST" "$PROG_SELFTEST" selftest_error.txt
    T0=$(date +%s)
    run_limited "$TIMEOUT_SELFTEST" ./"$EXE_SRC" --selftest-transcribe "$AUDIO_TEST" "$OUT_SELFTEST" "$PROG_SELFTEST"
    RC=$?
    T1=$(date +%s)
    if [ "$RC" -eq 0 ]; then ok "selftest exit=0 (tiempo $((T1 - T0))s para ${AUDIO_DUR}s de audio)"
    elif [ "$RC" -eq 124 ]; then fail "selftest timeout >${TIMEOUT_SELFTEST}s"
    else fail "selftest exit=$RC"; fi
    if [ -s "$OUT_SELFTEST" ]; then
        ok "texto generado ($(wc -c < "$OUT_SELFTEST") bytes)"
        if grep -qi "Transcribe faithfully" "$OUT_SELFTEST"; then warn "el resultado parece alucinación de whisper (audio demasiado débil?)"; fi
    else
        fail "selftest: resultado vacío"
    fi
    if [ -f "$PROG_SELFTEST" ] && grep -q "100%" "$PROG_SELFTEST"; then
        ok "progreso llegó a 100%"
    else
        fail "progreso no llegó a 100% ($([ -f "$PROG_SELFTEST" ] && tail -1 "$PROG_SELFTEST" || echo sin-log))"
    fi
    rm -f "$OUT_SELFTEST" "$PROG_SELFTEST" selftest_error.txt
else
    fail "Sin exe no hay selftest"
fi

# ── [4b] E2E UI DEL EXE (modo headless, sin entrada sintética) ───────────────
# Los flujos reales de la interfaz (asistente, Configuracion, UI principal,
# selectores y medicion de microfono) se ejecutan DENTRO del propio proceso
# del exe con --e2e-ui: funciona en cualquier entorno (CI, sandbox, segunda
# maquina) porque no depende de clics sinteticos ni del escritorio fisico.
run_e2e_ui() {
    local exe="$1" label="$2" failed=0 sc rc t0 t1
    for sc in wizard config widgets mic; do
        rm -f e2e_ui_result.txt e2e_ui_error.txt
        t0=$(date +%s)
        run_limited 180 ./"$exe" --e2e-ui "$sc" e2e_ui_result.txt
        rc=$?
        t1=$(date +%s)
        if [ "$rc" -eq 0 ] && [ -f e2e_ui_result.txt ] && grep -q "PASS" e2e_ui_result.txt; then
            ok "E2E-UI $sc ($label) exit=0 en $((t1 - t0))s"
        elif [ "$rc" -eq 124 ]; then
            fail "E2E-UI $sc ($label): timeout >180s"
            failed=1
        else
            fail "E2E-UI $sc ($label): rc=$rc"
            [ -f e2e_ui_result.txt ] && grep "FAIL" e2e_ui_result.txt | sed 's/^/      /' | tee -a "$LOG"
            [ -f e2e_ui_error.txt ] && sed 's/^/      /' e2e_ui_error.txt | tail -5 | tee -a "$LOG"
            failed=1
        fi
        rm -f e2e_ui_result.txt e2e_ui_error.txt
    done
    return "$failed"
}

step "[4b] Validación E2E de UI del exe: --e2e-ui wizard/config/widgets/mic"
if [ -f "$EXE_SRC" ]; then
    if run_e2e_ui "$EXE_SRC" onefile; then
        ok "E2E UI onefile: 3 escenarios en verde"
    else
        fail "E2E UI onefile: al menos un escenario fallo"
    fi
    if [ "$DO_ONEDIR" = 1 ] && [ -f "dist/AudioClass/AudioClass.exe" ]; then
        if run_e2e_ui "dist/AudioClass/AudioClass.exe" onedir; then
            ok "E2E UI onedir: 3 escenarios en verde"
        else
            fail "E2E UI onedir: al menos un escenario fallo"
        fi
    fi
else
    fail "Sin exe no hay E2E UI"
fi

# ── [5] WCAG SOBRE EL CÓDIGO EMPAQUETADO ─────────────────────────────────────
if [ "$DO_FULL_VALIDATION" = 1 ] && [ -f "$EXE_SRC" ]; then
    step "[5] Contraste WCAG del código empaquetado (run_wcag_on_exe.py)"
    T0=$(date +%s)
    run_limited "$TIMEOUT_WCAG_EXE" "$PY" -u run_wcag_on_exe.py
    RC=$?
    T1=$(date +%s)
    out=$(cat /tmp/_deploy_out.txt 2>/dev/null); rm -f /tmp/_deploy_out.txt
    if [ "$RC" -eq 0 ] && printf '%s' "$out" | grep -q "RESULTADO: TODO OK"; then
        ok "WCAG empaquetado: TODO OK en $((T1 - T0))s"
    elif [ "$RC" -eq 124 ]; then
        fail "WCAG empaquetado: timeout >${TIMEOUT_WCAG_EXE}s"
    else
        fail "WCAG empaquetado: FALLA (rc=$RC)"
        printf '%s\n' "$out" | tail -8 | sed 's/^/      /' | tee -a "$LOG"
    fi

    # Dialogo de microfono debil EJECUTADO contra el bytecode del exe:
    # fuerza p90 bajo y verifica que el medidor sube a verde, el running max
    # no baja y 'Continuar grabando' arranca la grabacion real.
    step "[5] Diálogo de micrófono débil del exe (test_mic_warn_on_exe.py)"
    run_tests test_mic_warn_on_exe "MIC_WARN_ON_EXE_OK"
fi

# ── [6] INTEGRIDAD DEL ZIP ───────────────────────────────────────────────────
step "[7] Integridad: exe del zip == entregable raíz"
"$PY" -c "
import zipfile, hashlib
z = zipfile.ZipFile(r'$ZIP_DEST')
data = z.read(r'$EXE_DEST')
local = open(r'$EXE_DEST', 'rb').read()
print('IDENTICOS' if hashlib.sha256(data).digest() == hashlib.sha256(local).digest() else 'DIFERENTES')
" > /tmp/_zipchk.txt 2>&1 && grep -q IDENTICOS /tmp/_zipchk.txt \
    && ok "SHA-256 del exe en zip == entregable raíz" \
    || { fail "El zip NO contiene el exe actual"; cat /tmp/_zipchk.txt | sed 's/^/      /' | tee -a "$LOG"; }
rm -f /tmp/_zipchk.txt

# ── RESUMEN ──────────────────────────────────────────────────────────────────
step "RESUMEN"
log "  OK: $PASS   FALLOS: $FAIL   Advertencias: $WARN"
ls -la --time-style=+%Y-%m-%d_%H:%M "$EXE_DEST" "$ZIP_DEST" 2>/dev/null | awk '{print "  ", $7, $6, $5, "bytes"}' >> "$LOG" || true
[ -f "$EXE_DEST" ] && log "  $EXE_DEST — $(stat -c%s "$EXE_DEST") bytes, $(stat -c%y "$EXE_DEST" | cut -d. -f1)"
[ -f "$ZIP_DEST" ] && log "  $ZIP_DEST — $(stat -c%s "$ZIP_DEST") bytes, $(stat -c%y "$ZIP_DEST" | cut -d. -f1)"

if [ "$FAIL" -gt 0 ]; then
    log ""
    log "${C_RED}RESULTADO: FALLA — $FAIL fallo(s). Revisa $LOG.${C_END}"
    exit 1
fi
log ""
log "${C_GRN}RESULTADO: PRODUCCIÓN LISTA [OK]${C_END}"
log "  Los usuarios finales reciben: $EXE_DEST (+ zip $ZIP_DEST)"
exit 0
