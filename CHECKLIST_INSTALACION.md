# CHECKLIST DE INSTALACIÓN Y VERIFICACIÓN — AudioClass v9.1

> **Objetivo:** validar la versión publicada de punta a punta en un **usuario limpio**
> (Windows sin AudioClass instalado previamente). Marca cada casilla con `[x]` al
> completarla. Si alguna falla, registra el error al final (sección ).

---

## 0. Preparación del entorno limpio

- [ ] Crear un **usuario de Windows nuevo** (o una máquina virtual / PC de prueba).
- [ ] Entrar con ese usuario y confirmar que **no existen**:
  - `%USERPROFILE%\AudioClass` (carpeta del programa)
  - `%USERPROFILE%\AudioClass_Recordings` (carpeta de grabaciones)
  - Acceso directo `AudioClass.lnk` en el escritorio
- [ ] Verificar que **no hay ningún proceso** `AudioClass.exe` corriendo:
  - `tasklist | findstr /i "AudioClass"` -> debe devolver **vacío**.
- [ ] Copiar el zip publicado `AudioClass_v9.1_COMPLETA.zip` al escritorio del usuario limpio.

---

## 1. Instalación desde el zip

- [ ] **Descomprimir el zip completo** en una carpeta (ej. `Desktop\AudioClass_v9.1`).
- [ ] Confirmar que la carpeta contiene al menos:
  - [ ] `AudioClass COMPLETA v9.1.exe`
  - [ ] `LEEME.txt`
- [ ] **Primera ejecución — SmartScreen**: el exe NO está firmado -> Windows muestra
      "Windows protegió tu PC". Pasos exactos para el usuario final:
      1. Pulsar **"Más información"** en el aviso azul.
      2. Pulsar **"Ejecutar de todos modos"**.
      - Si el exe viene de internet y no abre: clic derecho -> **Propiedades** ->
        marcar **"Desbloquear"** (junto a Seguridad) -> Aceptar -> abrir de nuevo.
      - **NO** recomendar desactivar SmartScreen ni el antivirus.
- [ ] Hacer **doble clic en `AudioClass COMPLETA v9.1.exe`** (o en `instalar_audioclass.bat` si se usa el flujo onedir).
- [ ] El instalador debe mostrar `[1/3]`, `[2/3]`, `[3/3]` y terminar en `LISTO`.
- [ ] Confirmar que se creó (flujo onedir):
  - [ ] `%USERPROFILE%\AudioClass\AudioClass.exe` (programa instalado)
  - [ ] Acceso directo **"AudioClass"** en el escritorio
- [ ] Responder **S** a "¿Quieres ABRIR AudioClass ahora?" (o abrir desde el acceso directo).
- [ ] **Google Docs**: en esta versión el botón "Google Docs" aparece
      **desactivado** ("no disponible"): el componente `google-auth-oauthlib` no
      viaja en el instalador. PDF/DOCX sí funcionan. Verificar que el botón está
      desactivado con etiqueta clara (no debe crashear al pulsarlo).

> **IMPORTANTE:** la primera apertura tarda **30-60 segundos** (descomprime la IA
> Whisper en segundo plano). Es normal. No cerrar la ventana durante ese tiempo.

---

## 2. Primer arranque (wizard)

- [ ] La ventana de **AudioClass** se abre sin errores visibles.
- [ ] Aparece el **asistente guiado** (wizard) del primer uso (first_run).
- [ ] Completar/omitir los pasos del asistente sin errores.
- [ ] La app crea la carpeta `%USERPROFILE%\AudioClass_Recordings` automáticamente.
- [ ] Revisar la **consola/terminal** (si se abrió): sin `Traceback` ni errores.

---

## 3. Configuración mínima

- [ ] Abrir **Configuración** y verificar que el **modo local** está seleccionado
      (transcripción offline con Whisper, sin internet).
- [ ] Si hay API Key de Gemini disponible (opcional): probar conexión en Configuración.
      Si no hay key, **no es bloqueante** para grabar y transcribir.
- [ ] Cerrar Configuración. La app vuelve al panel principal.

---

## 4. Grabar 1 minuto de voz

- [ ] Pulsar el botón **(grabar)**.
- [ ] Confirmar que el botón cambia a **Detener** en la MISMA posición (visible).
- [ ] Hablar claro durante **~60 segundos** (ej. leyendo un párrafo).
- [ ] Verificar durante la grabación:
  - [ ] El **VU meter** se mueve con la voz (nivel entre -45 dB y -12 dB).
  - [ ] El **cronómetro** avanza en tiempo real.
  - [ ] La **onda de audio** (waveform) se dibuja.
- [ ] Pulsar **Detener**.
- [ ] Confirmar que el botón vuelve a **(grabar)** en su posición original.
- [ ] Verificar que se crearon archivos en `%USERPROFILE%\AudioClass_Recordings`:
  - `clase_YYYYMMDD_HHMMSS_raw.wav` (audio original)
  - `clase_YYYYMMDD_HHMMSS_mejorado.wav` (audio con pipeline)

---

## 5. Transcribir (motor local paralelo)

- [ ] Pulsar **Transcribir** (sin "con tiempos" para la prueba rápida).
- [ ] Verificar que aparece **"Iniciando transcripción..."** y luego el progreso:
  - [ ] La **barra de progreso avanza de forma continua** dentro de cada chunk.
  - [ ] El texto muestra **porcentaje + tiempo restante** (`X% · ~Ys rest`).
  - [ ] Se ve el mensaje con **nº de núcleos y chunks** (`N núcleos · X/Y chunks`).
- [ ] Esperar a que termine. Verificar que la barra llega a **100%** y aparece el toast
      **"Transcripción completada"** (verde).
- [ ] Verificar que el **texto transcrito aparece** en el panel (≈ lo que se habló).
- [ ] Confirmar que se guardó `clase_..._transcripcion.txt` en `AudioClass_Recordings`.

> Si el audio fue solo ruido/estática, Whisper puede devolver texto vacío: se espera.
> La prueba de voz real debe producir texto legible.

---

## 6. Exportar a DOCX

- [ ] Pulsar **Guardar DOCX** (junto a "Guardar PDF").
- [ ] Elegir ubicación y nombre, y guardar.
- [ ] Abrir el `.docx` generado y verificar que contiene:
  - [ ] Título y encabezado
  - [ ] **Numeración de líneas** (`[  1]`, `[  2]`, ...)
  - [ ] **Timestamps** por segmento (`[mm:ss - mm:ss]`), si se transcribió con tiempos
  - [ ] Insignia **"Revisado por IA"** (o sección equivalente)
  - [ ] Modelo usado (ej. `tiny`)
- [ ] (Opcional) Repetir con **Guardar PDF** y abrirlo: mismo contenido.

---

## 7. Verificar que no quedan procesos abiertos

- [ ] Cerrar AudioClass (X de la ventana).
- [ ] Esperar 5 segundos.
- [ ] Ejecutar en CMD:
  ```cmd
  tasklist | findstr /i "AudioClass"
  ```
- [ ] Resultado esperado: **sin líneas** (proceso terminado limpiamente).
- [ ] Verificar también que **no quedó** un proceso `python.exe` de AudioClass:
  ```cmd
  tasklist | findstr /i "python"
  ```
  (Si hay otros Python corriendo del usuario, distinguirlos por la ruta del ejecutable;
  ninguno debe apuntar a `%USERPROFILE%\AudioClass`.)

> Si al cerrar durante una transcripción el proceso tarda unos segundos en salir,
> es normal (drena el pool de chunks en curso, máximo ~90s). Pasado ese tiempo, debe
> desaparecer.

---

## 8. Reapertura y persistencia

- [ ] Abrir AudioClass de nuevo desde el acceso directo (2ª apertura, debe ser más rápida).
- [ ] Confirmar que **no reaparece el wizard** (first_run ya se guardó).
- [ ] Confirmar que **las grabaciones anteriores siguen** en el historial.
- [ ] Cerrar de nuevo y verificar que el proceso termina (paso 7).

---

## 9. Desinstalación (opcional, al final)

- [ ] Cerrar AudioClass.
- [ ] Doble clic en **`desinstalar_audioclass.bat`**.
- [ ] Confirmar que elimina:
  - [ ] Acceso directo del escritorio
  - [ ] `%USERPROFILE%\AudioClass`
- [ ] Confirmar que **conserva** `%USERPROFILE%\AudioClass_Recordings` (datos del usuario).

---

## Resumen

| Fase | Estado |
|---|---|
| 0. Entorno limpio | [ ] |
| 1. Instalación desde zip | [ ] |
| 2. Primer arranque | [ ] |
| 3. Configuración mínima | [ ] |
| 4. Grabar 1 min | [ ] |
| 5. Transcribir | [ ] |
| 6. Exportar DOCX | [ ] |
| 7. Sin procesos abiertos | [ ] |
| 8. Reapertura | [ ] |
| 9. Desinstalación | [ ] |

**RESULTADO GLOBAL:** [ ] APROBADO  ·  [ ] RECHAZADO

---

## Registro de errores encontrados

| # | Fase | Fecha/Hora | Descripción del error | Solución aplicada |
|---|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |

---

*Checklist generado para la auditoría pre-lanzamiento de AudioClass v9.1.*
