# 🛡️ REVISIÓN DE CIBERSEGURIDAD Y EXPOSICIÓN LEGAL — AudioClass v9.1

> **Objetivo:** identificar riesgos de seguridad y de responsabilidad legal (reclamaciones de usuarios, docentes, corporaciones y autoridades) derivados del uso y distribución de AudioClass, y dar un plan accionable para reducirlos.
>
> **Fecha:** 12 agosto 2026 · **Alcance:** app de escritorio Windows (`audioclass_v91.py` + `audioclass_core.py`), servidor Colab opcional (`audioclass_colab_server_v91.py`), exe empaquetado (onefile/onedir), config y datos de usuario.
>
> ⚠️ **Aviso legal:** este documento es una revisión técnica de riesgos con fines informativos. **No constituye asesoría legal.** Las normas citadas deben validarse con un abogado según la jurisdicción, el uso concreto y el rol (usuario individual, centro educativo, empresa). Ningún documento elimina la responsabilidad; la reduce y la documenta.

---

## 1. Resumen ejecutivo

AudioClass graba audio de clases/reuniones, lo transcribe **localmente** (faster-whisper, sin internet) y opcionalmente lo analiza con **IA de terceros** (Gemini o OpenAI). La combinación "grabación de personas + envío a terceros" la coloca en la categoría de **tratamiento de datos personales**, con obligaciones legales aunque no se comercialice.

**Veredicto:** el riesgo técnico-legal es **GESTIONABLE** hoy con acciones de bajo coste, y hay una brecha principal: **no existe aviso de privacidad ni consentimiento dentro de la app** antes de que las transcripciones salgan hacia Gemini/OpenAI, y el **servidor Colab expone la API key en URLs** (filtrable a logs/historial).

**Prioridad absoluta (P0):**
1. Aviso de privacidad y consentimiento explícito en la app (antes del primer uso y antes del primer análisis con IA).
2. Endurecer el servidor Colab (key fuera de URLs, límite de subida, rate-limit).
3. Plantillas legales distribuidas con la app (EULA + política de privacidad + aviso de grabación).

---

## 2. Metodología

Revisión de código fuente (GUI, núcleo, servidor Colab, empaquetado), auditoría funcional previa (7 frentes, tests en verde, WCAG AA), y análisis de flujos de datos. Se contrastaron los hallazgos con el marco legal aplicable a grabación de audio, datos personales, datos educativos y uso corporativo.

---

## 3. Inventario de datos y flujos de información

| # | Dato | Dónde vive | ¿Sale de la máquina? | Base legal que aplica |
|---|---|---|---|---|
| D1 | Grabaciones de audio (clases/reuniones) | `~/AudioClass_Recordings/*.wav` | No (local) — salvo que el usuario suba al servidor Colab | GDPR/LOPDGDD art. 6 (consentimiento), leyes de grabación |
| D2 | Transcripciones | `~/AudioClass_Recordings/` + exportaciones PDF/DOCX/GDocs | **SÍ** si se usa "Adaptación Inteligente" (Gemini/OpenAI) o se suben al Colab | GDPR art. 5/6/13 (transparencia), DPIA si es a gran escala |
| D3 | Config + API keys (Gemini, OpenAI, Colab) | `~/AudioClass_Recordings/audioclass_config.json` | No (local); la key de Colab SÍ viaja en la URL | Obligación de seguridad (GDPR art. 32) |
| D4 | Logs de errores | `~/AudioClass_Recordings/logs/audioclass.log` | No | Retención y minimización (GDPR art. 5) |
| D5 | Voz del usuario (medición de micrófono) | Temporal, `mic_voz_user.wav` | No | — |
| D6 | Audio/PDF en servidor Colab (opcional, self-hosted) | En la sesión de Colab del propio usuario | Sí (nube de Google/el usuario) | Responsabilidad del usuario que lo despliega |

**Flujo crítico:** Grabación (local) → Transcripción (local) → **Análisis con IA = envío de la transcripción a `generativelanguage.googleapis.com` o `api.openai.com`**. Este envío ocurre sin que la app muestre un aviso de privacidad previo.

---

## 4. Marco legal aplicable (según jurisdicción y uso)

### 4.1 Protección de datos personales
- **GDPR (UE) / LOPDGDD (España):** el usuario de la app actúa como *responsable del tratamiento*; la app es la herramienta. Obliga a: licitud (consentimiento o interés legítimo), transparencia (informar qué se graba y por qué), minimización, seguridad (art. 32), derechos ARCO/ARSULIPO (acceso, rectificación, supresión, portabilidad), y **DPIA** si el tratamiento es a gran escala o de categorías especiales.
- **LGPD (Brasil):** mismo esquema (bases legales, derechos del titular, ANPD).
- **CCPA/CPRA (California) y leyes estatales de EE. UU.:** derechos de acceso/borrado/opt-out; aplica si hay usuarios californianos (la app es global vía descarga).
- **FERPA (EE. UU., educación):** si un centro educativo usa la app con transcripciones de clases, las grabaciones pueden ser "education records" → políticas de acceso, retención y consentimiento de los padres/estudiantes.
- **COPPA (EE. UU., menores de 13):** prohibido recopilar datos de menores sin consentimiento parental verificable. Una app que graba aulas debe **asumir que graba menores** y desactivar el envío a IA por defecto, o exigir verificación.

### 4.2 Grabación de conversaciones (consentimiento)
- **España (LOPDGDD art. 90 + Código Penal):** grabar conversaciones *privadas* sin consentimiento de los participantes puede ser ilícito; grabar en el ámbito laboral exige información previa a los empleados (ET art. 20.3).
- **EE. UU.:** 38 estados son *one-party consent*; pero **California, Florida, Illinois, Maryland, Massachusetts, Michigan, Montana, Nevada, New Hampshire, Oregon, Pennsylvania, Vermont, Washington** (y D.C.) son *two-party/all-party consent*: **todos** los participantes deben saber y consentir la grabación.
- **Consecuencia práctica:** un usuario que graba a otros sin avisarlos puede exponerse a reclamaciones **civiles y penales**; la app debe facilitar el cumplimiento (aviso visible, flujo de consentimiento), no impedirlo.

### 4.3 Uso corporativo y laboral
- Grabar reuniones/llamadas de empleados = **monitoreo laboral**: exige información previa, proporcionalidad y finalidad legítima (GDPR art. 88, ET art. 20.3).
- Corporaciones que suben transcripciones de reuniones a Gemini/OpenAI sin revisar los términos de esos proveedores pueden violar su propia política de datos; el **DPA (Data Processing Agreement)** con el proveedor de IA es obligatorio para ellas.
- Reclamaciones típicas de corporaciones: fuga de secretos comerciales vía IA, grabaciones sin consentimiento de asistentes, incumplimiento de retención.

### 4.4 Accesibilidad (demandas ADA/WCAG)
- Las demandas por sitios/apps inaccesibles son una de las vías de litigio más frecuentes en EE. UU. **AudioClass ya cumple contraste WCAG AA y lo valida en cada despliegue** (run_wcag_on_exe). Esto es un activo: mantenerlo y documentarlo reduce el vector de demanda por accesibilidad.

---

## 5. Hallazgos de seguridad (auditoría real del código)

| ID | Severidad | Hallazgo | Evidencia | Mitigación |
|---|---|---|---|---|
| H1 | 🔴 Alta | **Sin aviso de privacidad ni consentimiento en la app** antes de enviar transcripciones a Gemini/OpenAI. El asistente de primer uso pregunta por la API key, pero no informa de que el texto saldrá a servidores de terceros. | `audioclass_v91.py` (wizard + `_adapt`) | Aviso + checkbox de consentimiento en wizard y en Configuración; opción "procesar todo local" sin IA |
| H2 | 🔴 Alta | **Servidor Colab: API key en la URL** (`/download?file=…&key=…`, `/compile?…&key=…`) → se filtra a logs de ngrok/Colab, historial y proxies. | `audioclass_colab_server_v91.py` L357-363 | Header `X-API-Key` (ya hay HMAC con `compare_digest`); nunca key en query string |
| H3 | 🟠 Media | **Colab: sin límite de tamaño de subida ni rate-limit.** Un túnel público con la key permite abusos (coste de Colab, almacenamiento, abuso del endpoint). | `audioclass_colab_server_v91.py` | Tope de MB (p. ej. 200 MB), rate-limit por IP/key, token de sesión |
| H4 | 🟠 Media | **Sin cifrado en reposo de grabaciones/transcripciones.** Las keys se cifran con DPAPI (bien), pero los WAV/transcripciones en `~/AudioClass_Recordings` van en claro. | `audioclass_v91.py` L108 | Documentar; ofrecer "carpeta cifrada" (BitLocker/EFS) como opción para uso corporativo |
| H5 | 🟠 Media | **El exe no está firmado** → SmartScreen avisa. No es un riesgo de seguridad del código, pero erosiona la confianza y puede alegarse en una reclamación de "software no confiable". | FIRMAR.md | Firmar con certificado (EV/OV) o documentar el proceso de verificación de hash |
| H6 | 🟡 Baja | **Transcripción con alucinaciones**: el selftest ya detecta frases plantilla de whisper. Un transcript erróneo presentado como fiel puede dar lugar a reclamaciones (especialmente en ámbitos legales/médicos). | `test_*` selftest, warning en `desplegar_produccion.sh` | Disclaimer en cada exportación: "transcripción automática, puede contener errores" |
| H7 | 🟡 Baja | **Logs con rutas/nombres de archivo** (no contenido, pero metadatos). | `~/AudioClass_Recordings/logs/` | Rotación y retención limitada (p. ej. 30 días) |
| H8 | ✅ Control existente | Keys cifradas con **DPAPI** ligado al usuario; config fuera de la carpeta de la app; transcripción local sin red; **WCAG AA validado en cada build**. | `_SECRET_FIELDS`, DPAPI | Mantener y documentar |

---

## 6. Análisis de riesgo por perfil de usuario

| Perfil | Riesgo principal | Exposición si falla | Mitigación clave |
|---|---|---|---|
| **Usuario individual** (graba sus propias clases) | Menor. Graba su propia voz y la del profesor con consentimiento implícito del aula | Reclamación por grabar a terceros sin aviso | Aviso de grabación visible; desactivar IA por defecto |
| **Docente/estudiante** (graba clases ajenas) | **Alto.** Menores en el audio (COPPA/FERPA), dos-party consent en varios estados | Demandas de padres, sanción del centro | Consentimiento del centro; modo "sin IA"; aviso en cada grabación |
| **Corporación** (reuniones, capacitación) | **Alto.** Monitoreo laboral + secretos comerciales hacia la IA | Reclamaciones laborales, fuga de datos, multas GDPR | Aviso a empleados, DPA con proveedor de IA, retención definida |
| **Profesional regulado** (legal/salud/educación) | **Medio-alto.** Transcripts usados como evidencia/proceso | Impugnación por errores de transcripción (H6) | Disclaimer visible + verificación humana |
| **Autoridades/auditoría** | — | Multas por tratamiento sin base legal | Consentimiento documentado, DPIA si aplica |

---

## 7. Plan de acción priorizado

### 🔴 P0 — Esta semana (reduce el riesgo de forma inmediata)
1. **Aviso + consentimiento en la app (H1):**
   - En el asistente de primer uso: "🔒 Tus transcripciones se procesan localmente. Si activas el análisis con IA (Gemini/OpenAI), **el texto se envía a servidores de Google/OpenAI**. ¿Aceptas?" con checkbox.
   - Botón en Configuración: "Ver aviso de privacidad" que muestre el texto de la plantilla §8.2.
   - Opción global "No enviar nunca datos a IA" (default recomendado: OFF para IA).
2. **Endurecer el servidor Colab (H2/H3):** key vía header `X-API-Key`, tope de subida, rate-limit simple, `pip install` bajo `if __name__ == "__main__"`.
3. **Distribuir las plantillas legales** (§8) dentro del zip: `AVISO_DE_PRIVACIDAD.txt`, `EULA.txt`.

### 🟠 P1 — Este mes
4. **Disclaimer en exportaciones (H6):** añadir "Transcripción automática — puede contener errores" en el pie de cada PDF/DOCX y al exportar a Google Docs.
5. **Retención y borrado:** botón "Borrar todas mis grabaciones" y documentar retención de logs (30 días).
6. **Firma del exe (H5):** iniciar proceso con certificado OV/EV (o al menos publicar el SHA-256 oficial en la web del proyecto).
7. **Cifrado en reposo (H4):** documentar BitLocker/EFS para la carpeta de grabaciones en guías corporativas.

### 🟡 P2 — Próximos meses
8. **DPIA** del tratamiento (obligatorio si se vende a centros educativos a gran escala).
9. **DPA** modelo para que corporaciones/centros lo firmen con el proveedor de IA (o con el usuario como responsable).
10. **Registro de actividad** para auditoría (quién exportó qué y cuándo) sin almacenar contenido.

---

## 8. Plantillas listas para usar

### 8.1 Aviso de grabación (mostrar antes de la primera grabación y exportar)
> **AVISO DE GRABACIÓN.** AudioClass graba audio para transcribir y organizar clases/reuniones. Al usar esta app con otras personas, debes informarles de que la sesión se está grabando y obtener su consentimiento cuando la ley lo exija (en particular en estados de consentimiento de todos los participantes y en entornos laborales). Tú eres responsable del uso legal de las grabaciones.

### 8.2 Aviso de privacidad (para el diálogo de Configuración)
> **PRIVACIDAD.** Tus grabaciones y transcripciones se procesan **en tu propio equipo** y se guardan en `~/AudioClass_Recordings`. Si activas el **análisis con IA**, el texto de la transcripción se envía a servidores de **Google (Gemini)** u **OpenAI**, según el proveedor elegido, para generar resúmenes, guías y exámenes. No compartas transcripciones con información sensible si no aceptas ese envío. Las claves de API se guardan cifradas en tu equipo. Puedes borrar tus grabaciones en cualquier momento.

### 8.3 Cláusulas EULA (extracto para el texto de licencia)
> - **Uso legal:** el usuario es el responsable del tratamiento de los datos que graba y se obliga a obtener los consentimientos exigidos por la ley (grabación de terceros, menores, ámbito laboral) y a no usar la app para actividades ilícitas.
> - **Sin garantía de exactitud:** las transcripciones son automáticas y pueden contener errores; no constituyen acta oficial, asesoría profesional ni evidencia certificada.
> - **Sin garantía de disponibilidad:** el software se entrega "tal cual", sin garantías de funcionamiento ininterrumpido; el usuario respalda sus grabaciones.
> - **IA de terceros:** el análisis con IA depende de servicios de Google/OpenAI sujetos a sus propios términos; el usuario decide activarlo.
> - **Limitación de responsabilidad:** el autor no será responsable de daños indirectos o pérdida de datos derivados del uso del software, en la máxima medida permitida por la ley aplicable.
> - **Accesibilidad:** el software cumple contraste WCAG AA; defectos de accesibilidad se atienden a través del canal de soporte.

### 8.4 Esqueleto de Política de Privacidad (para la web del proyecto)
> 1. **Responsable:** [nombre/empresa], [contacto]. 2. **Datos tratados:** audio y transcripciones generadas por el usuario; config y claves cifradas. 3. **Finalidad:** transcripción y organización de clases/reuniones. 4. **Base legal:** consentimiento del usuario. 5. **Destinatarios:** proveedores de IA (Google/OpenAI) solo si el usuario activa el análisis; servidor Colab solo si el usuario lo despliega. 6. **Transferencias internacionales:** envíos a servidores de EE. UU. bajo cláusulas contractuales tipo (SCC) de los proveedores. 7. **Derechos:** acceso, rectificación, supresión, portabilidad; contacto para ejercerlos. 8. **Retención:** las grabaciones se conservan hasta que el usuario las borre; logs 30 días. 9. **Menores:** no se dirige a menores de 13; si se usa en aulas, el centro debe gestionar el consentimiento parental. 10. **Seguridad:** cifrado local de claves (DPAPI), procesamiento local por defecto, WCAG AA.

### 8.5 Aviso para corporaciones (adjuntar a la guía de uso corporativo)
> **USO CORPORATIVO.** Si AudioClass se usa para grabar reuniones o comunicaciones de empleados: (1) informa previamente a los participantes y obtén su consentimiento conforme a la ley laboral y de protección de datos aplicable; (2) no subas transcripciones con información confidencial a servicios de IA sin revisar el acuerdo de tratamiento de datos (DPA) con el proveedor; (3) define un periodo de retención y un responsable del tratamiento; (4) valida que el uso cumple tu política interna de datos.

---

## 9. Plan de respuesta a incidentes (mínimo viable)

| Fase | Acción | Responsable |
|---|---|---|
| Detección | El usuario reporta fuga (grabación filtrada, key expuesta, uso indebido de la cuenta de IA) | Soporte |
| Contención | Rotar la API key afectada; revocar el túnel Colab; pausar el envío a IA | Usuario |
| Evaluación | Determinar qué datos salieron y a quién afectan (¿menores? ¿empleados?) | Usuario + abogado |
| Notificación | Notificar a los afectados y a la autoridad si la ley lo exige (72 h GDPR) | Usuario |
| Mejora | Actualizar la app, el aviso y los controles (rate-limit, consentimiento) | Desarrollador |
| Registro | Documentar el incidente en `PROGRESO_AUDITORIA.md` con fecha y acciones | Desarrollador |

---

## 10. Checklist de cumplimiento (verificable)

- [ ] Aviso de privacidad visible en la app (wizard + Configuración) *(H1)*
- [ ] Consentimiento explícito para envío a IA, desactivado por defecto *(H1)*
- [ ] Servidor Colab: key en header, tope de subida, rate-limit *(H2/H3)*
- [ ] Disclaimer de transcripción automática en exportaciones PDF/DOCX/GDocs *(H6)*
- [ ] EULA + Política de Privacidad distribuidos con la app *(§8.3/§8.4)*
- [ ] Botón de borrado de grabaciones + retención de logs 30 días *(P1)*
- [ ] WCAG AA revalidado en cada despliegue (ya se hace) *(§4.4)*
- [ ] SHA-256 oficial publicado para verificación del exe *(H5)*
- [ ] DPIA si se despliega en centros educativos/empresas a gran escala *(P2)*

---

## 11. Anexo — Referencias normativas
- GDPR (Reglamento UE 2016/679), arts. 5, 6, 13, 32, 88 · LOPDGDD (Ley Orgánica 3/2018, art. 90) · ET (Real Decreto Legislativo 2/2015, art. 20.3)
- LGPD (Ley 13.709/2018, Brasil) · CCPA/CPRA (Cal. Civ. Code §1798.100)
- FERPA (20 U.S.C. §1232g) · COPPA (15 U.S.C. §§6501-6506)
- Leyes estatales de consentimiento de grabación (two-party: CA, FL, IL, MD, MA, MI, MT, NV, NH, OR, PA, VT, WA, DC)
- ADA / WCAG 2.1 AA (accesibilidad)

---

## 12. Vectores de demanda investigados en la web (agosto 2026) — apps creadas con IA

Investigación de las principales causas de litigio contra software generado con IA ("vibe coding") y apps de transcripción/grabación, con su aplicación a AudioClass y su estado:

### 12.1 ⚖️ Grabar sin consentimiento (el vector Nº1 para esta app)
- **Caso Otter.ai (class action, ago 2025, EE. UU.):** demanda contra el transcriptor de reuniones por (1) **grabar conversaciones privadas sin consentimiento** (leyes de interceptación federales y estatales, CIPA §§631-632) y (2) **usar las conversaciones para entrenar sus modelos de IA** sin permiso. Es el precedente más directo para una app de grabación+transcripción.
- **Leyes estatales:** 11-13 estados exigen consentimiento de TODOS los participantes (CA, FL, IL, MD, MA, MI, MT, NV, NH, OR, PA, VT, DC). Grabar sin consentimiento = responsabilidad civil y penal.
- **Estado en AudioClass:** ✅ **CUBIERTO** — (a) asistente de primer uso con aviso y casilla obligatoria; (b) **aviso de grabación al iniciar la primera grabación** (`_begin_recording`: sin aceptar no se graba; queda guardado en config); (c) el indicador **"● GRABANDO"** es visible durante toda la grabación (nada de grabación oculta, el problema central del caso Otter).

### 12.2 🤖 La empresa responde por lo que dice su IA
- **Moffatt v. Air Canada (2024, BC CRT):** la aerolínea fue condenada por la información errónea de su chatbot; el tribunal rechazó que "el chatbot actuaba solo". Precedente: **lo que genera la IA se atribuye al que la despliega**.
- **Estado en AudioClass:** ➕ **ARREGLADO parcialmente** — las exportaciones (PDF/DOCX/GDocs/Colab) y los archivos de adaptación ahora llevan el aviso "**Transcripción/Contenido generado por IA — puede contener errores. No constituye acta oficial**". Es la mitigación documentada del precedente Air Canada (el usuario sabe que es contenido automático).

### 12.3 💥 Daños por contenido generado (suicidios, consejos dañinos)
- **Character.AI / OpenAI (2024-2026):** demandas por muerte de menores vinculadas a chatbots; Google y Character.AI llegaron a acuerdos (ene 2026). También demandas por alucinaciones que difaman personas (NOYB vs. OpenAI, abr 2024).
- **Estado en AudioClass:** el análisis con IA genera resúmenes/guías de ESTUDIO (no consejos terapéuticos ni jurídicos). ✅ **CUBIERTO** — disclaimers en todas las salidas + **los avisos de privacidad ahora indican explícitamente que el contenido no es consejo médico/legal ni acta oficial**, y el envío a IA requiere consentimiento explícito. Recomendación P2: restringir por edad/uso declarado si se distribuye a menores.

### 12.4 📚 Copyright y licencias del código generado por IA (vibe coding)
- **Doe v. GitHub, Microsoft y OpenAI (2022-2024):** la mayoría de reclamaciones fueron desestimadas (jul 2024), pero **sobrevivieron las de incumplimiento de licencia/atribución** de código open source reproducido sin atribución.
- **Riesgo específico del vibe coding:** el modelo puede reproducir código GPL/AGPL sin atribución → **contaminación de licencia** (el peor caso: obligar a liberar la app). El código generado por IA puede además **carecer de protección de copyright** (requisito de autoría humana) pero **sí infringir el de otros** — "toda la responsabilidad, ninguna protección".
- **Estado en AudioClass:** ➕ **ARREGLADO** — se verificó que **todas las dependencias son permisivas** (MIT/BSD/Apache; fpdf2 LGPL por enlace dinámico; PyInstaller GPL con excepción de bootloader) → **sin contaminación copyleft**. Se añadió **`TERCEROS_Y_LICENCIAS.md`** (atribución requerida) y **`LICENCIA.txt`** (licencia explícita de la app, plantilla MIT por completar).

### 12.5 🧾 Publicidad engañosa de IA ("AI washing")
- **FTC Operation AI Comply (sep 2024-2026):** acciones contra empresas por prometer resultados de IA sin respaldo ("AI lawyer", generación de ingresos, moderación falsa). No hay "exención de IA" en las leyes de publicidad.
- **Estado en AudioClass:** ✅ **CUBIERTO** — sin claims engañosos (grep de overclaims en app/LEEME/GUÍA: limpio); el claim "máxima precisión" del asistente se suavizó a "**mayor precisión**" (comparativo factual); la insignia "✓ Revisado por IA" es factual y va acompañada del disclaimer de errores.

### 12.6 ♿ Demandas por accesibilidad (ADA/WCAG)
- Más de **4.000-5.000 demandas/año** en EE. UU. por sitios y apps inaccesibles; legislación en curso (Websites and Software Applications Accessibility Act 2025) que podría extenderlo a software de escritorio.
- **Estado en AudioClass:** ➕ **YA CUMPLE (activo existente)** — contraste WCAG 2.1 AA validado en cada despliegue (run_wcag_on_exe) sobre el bytecode empaquetado. Mantener y documentar.

### 12.7 🛡️ GDPR/privacidad y uso de datos de usuarios por terceros
- **NOYB vs. OpenAI (abr 2024):** reclamación por alucinaciones sobre personas (inexactitud, art. 5.1.d) y falta de corrección; Italia multó a OpenAI con 15 M€ (dic 2024). Los datos enviados a APIs de IA se retienen por defecto en el proveedor (Gemini API: hasta 55 días para abuso, sin entrenamiento; OpenAI API: sin entrenamiento desde mar 2023).
- **Estado en AudioClass:** ✅ **CUBIERTO** — la app **declara y pide consentimiento** (opt-in) antes de cualquier envío a Gemini/OpenAI; los avisos (asistente, diálogo de consentimiento y Configuración) ahora **mencionan la retención del proveedor** (Gemini hasta 55 días; OpenAI sin entrenamiento). Usuarios con configs antiguas ven el diálogo en el primer uso de IA.

### 12.8 🔒 Seguridad del código (auditoría interna, hallazgos reales)
- **Path traversal en `/download` del servidor Colab** (leer archivos fuera del directorio temporal): ➕ **ARREGLADO** (validación `resolve()` + `is_relative_to`).
- **API key en URLs** (filtrable a logs de ngrok/historial): ➕ **ARREGLADO** (header `X-API-Key`, URLs generadas sin clave).
- **Sin límite de subida ni rate-limit** en Colab: ➕ **ARREGLADO** (tope 200 MB, 30 peticiones/min por clave).
- **`pip install` en cada import** del servidor: ➕ **ARREGLADO** (solo bajo `__main__`).

## 13. Arreglos aplicados (12 agosto 2026)

| Archivo | Cambio | Vector que cubre |
|---|---|---|
| `audioclass_v91.py` | Asistente: tarjeta "Privacidad y consentimiento" (casilla obligatoria + opt-in de IA + retención del proveedor + "no es consejo médico/legal") | 12.1, 12.2, 12.3, 12.7 |
| `audioclass_v91.py` | Aviso de grabación al iniciar la primera grabación (sin aceptar no se graba) | 12.1 |
| `audioclass_v91.py` | "máxima precisión" → "mayor precisión" (claim factual) | 12.5 |
| `audioclass_v91.py` | Nota "generado automáticamente — verifica" dentro del panel de adaptación | 12.2 |
| `audioclass_v91.py` | `_adapt` no envía nada a IA sin consentimiento (diálogo `_prompt_ia_consent`, revocable en Configuración) | 12.7, 12.2 |
| `audioclass_v91.py` | Diálogo de Configuración: sección "🔒 Privacidad" con checkbox de consentimiento | 12.7 |
| `audioclass_v91.py` | Disclaimers en exportaciones PDF/DOCX/GDocs y en archivos de adaptación | 12.2, 12.5 |
| `audioclass_colab_server_v91.py` | Anti path-traversal en `/download`; key por header `X-API-Key`; URLs sin clave; rate-limit 30/min; tope de subida 200 MB; `pip install` bajo `__main__`; disclaimer en PDF generado | 12.8 |
| `audioclass_colab_server_v91.py` | **Headers de seguridad en todas las respuestas** (middleware): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: default-src 'none'` | 12.8 |
| `.gitignore` | `.env*` ignorado como red de seguridad (la app guarda las claves cifradas con DPAPI en `audioclass_config.json`, mejor que `.env` para escritorio) | 12.7, 12.8 |
| `.github/workflows/release.yml` (nuevo) | Post-producción automática: tag `v*` → compila onefile+onedir en CI, selftests + WCAG empaquetados, zips con documentos legales y GitHub Release (rollback por tags) | 12.8 |
| `TERCEROS_Y_LICENCIAS.md` (nuevo) | Atribución de todas las dependencias (MIT/BSD/Apache/LGPL-dinámico) | 12.4 |
| `LICENCIA.txt` (nuevo) | Licencia explícita de la app (MIT, plantilla) | 12.4 |
| `test_colab_server_security.py` | 11 tests del endurecimiento (path traversal, header, rate-limit, tope, URLs sin clave, **4 headers de seguridad**) | 12.8 |

**Validación:** `test_colab_server_security.py` **11/11** · `test_privacy_consent.py` **9/9** (incluye el gate de grabación) · `test_wcag_contrast` TODO OK (nuevos widgets pasan contraste) · `ADAPT_ENGINES_ALL_OK` · `EXPORT_OK` · `SMOKE_OK` · `py_compile` OK.

## 14. Pendiente (P1/P2, recomendado)

- [x] Aviso de grabación al iniciar grabación + indicador GRABANDO visible — ✅ hecho
- [x] Retención del proveedor mencionada en los avisos de IA — ✅ hecho
- [ ] Publicar el SHA-256 oficial del exe y firmar con certificado — P1
- [ ] Botón "Borrar todas mis grabaciones" + rotación de logs (30 días) — P1
- [ ] DPIA si se despliega en centros educativos/empresas — P2
- [x] `LICENCIA.txt` completada (© Daniel Pérez) + `EULA.txt` + `AVISO_DE_PRIVACIDAD.txt` + `TERCEROS_Y_LICENCIAS.md` — ✅ hecho e integrados en el zip del despliegue

---

*Documento generado como apoyo técnico-legal; revisar con asesoría legal antes de su uso en producción o distribución comercial.*
