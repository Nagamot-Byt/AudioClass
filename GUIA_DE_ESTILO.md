# AudioClass — Guía de Estilo (v9.2 "Académica Profesional")

Sistema de diseño para **AudioClass**: grabación de audio y transcripción automática con IA
para estudiantes, investigadores y profesionales. El objetivo es transmitir **rigor académico**:
orden, jerarquía, claridad y confianza — como un manual de laboratorio o una plataforma de
publicación científica.

> Implementado en `audioclass_v91.py` (paleta `PALETTES`, tipografía `_resolve_fonts`, tema
> persistente `config["theme"]`). Prototipo interactivo: `assets/ui_preview.html`.

---

## 1. Paleta de colores

| Token | HEX | Uso |
|---|---|---|
| Azul marino `bg` (dark) / `header` | `#0A1F44` | Fondo principal y barra superior |
| Azul marino claro `card` | `#12264E` | Tarjetas, paneles, sidebar |
| Gris pizarra `muted` / `button` | `#4A5568` / `#1E293B` | Texto secundario, pistas, relleno de pills |
| Blanco roto `bg` (light) | `#F5F7FA` | Fondo en modo claro |
| Blanco `card` (light) | `#FFFFFF` | Tarjetas en modo claro |
| **Dorado académico `accent`** | `#D4AF37` | **Botones primarios, progreso, foco, acentos** |
| Dorado oscuro `accent_hover` | `#B8860B` | Hover de botones primarios |
| Verde éxito `ok` | `#10B981` | Toasts de éxito, insignia "Revisado por IA", pasos completados |
| Ámbar `warn` | `#D97706` | Avisos (micro bajo, carga de modelo) |
| Rojo `err` | `#EF4444` | **Solo errores críticos** y grabación activa |
| Bordes `border` | `#1E3A6E` (dark) / `#E5E7EB` (light) | Separadores, contornos de tarjetas |
| Violeta `cloud` | `#8B5CF6` | Motor Cloud / Colab |

**Contraste:** todos los pares texto/fondo cumplen ≥ 4.5:1 (texto `#E8EDF7` sobre `#0A1F44` ≈ 13:1;
dorado `#D4AF37` sobre azul marino ≈ 7:1; `#B8860B` sobre blanco ≈ 4.6:1).

## 2. Tipografía

| Rol | Familia (orden de búsqueda) | Peso | Tamaño / Interlineado |
|---|---|---|---|
| Encabezados (H1/H2/H3) | **Merriweather** -> Georgia -> Cambria | 600/700 | 28 / 22 / 18 px · 1.3 |
| Título de app (header) | Merriweather -> Georgia | 700 | 21 px |
| Cuerpo y menús | **Inter** -> Segoe UI -> Tahoma | 400/500 | 16 px · 1.5 |
| Transcripción / código | **Source Code Pro** -> Consolas -> Courier New | 400 | 14 px (11 pt en UI) |

Las fuentes DejaVu empaquetadas (`assets/DejaVuSans.ttf` y `-Bold`) se registran con
`ctk.FontManager.load_font` para acentos y glifos unicode en el .exe.

> **Unificación (13 ago 2026):** la jerarquía tipográfica se aplica en TODA la
> interfaz — asistente de primer arranque, diálogo de Configuración, guía,
> prueba/optimizador de micrófono y VU meter usan ahora los tokens del sistema
> (`self.FH` para títulos serif, `self.FB` para cuerpo/controles sans). Ya no
> hay fuentes hardcodeadas sueltas; `_btn`, `_lbl` y `_entry` resuelven el
> default desde el mismo sistema de diseño.

## 3. Espaciado (cuadrícula de 8 px)

Margen exterior de tarjetas: **22 px** · padding interno de tarjetas: **18 px** · gutter entre
tarjetas: **10–16 px** · altura de botón estándar: **40 px** · radio de esquina: **12 px**
(tarjetas), **10 px** (botones), **32 px** (botón de grabación circular).

## 4. Layout

- **Header (56 px):** azul marino, logo + título serif, estado de conexión (motor local/cloud)
  y toggle de tema /. Subrayado dorado institucional.
- **Sidebar (300 px):** "Historial de Clases", lista de grabaciones tipo tarjeta, acciones
  (Reproducir, Transcribir, Eliminar, Guía, Configuración).
- **Panel principal:** grabación (botón circular + VU meter + cronómetro) -> configuración ->
  progreso -> waveform -> adaptación IA -> transcripción -> barra inferior.
- **Barra inferior (48 px):** ruta de guardado, atajos de teclado, temporizador.

## 5. Componentes y estados

| Componente | Default | Hover | Active | Disabled |
|---|---|---|---|---|
| Botón primario (dorado) | `#D4AF37`, texto blanco | `#B8860B` | escala 0.95 | `#9CA3AF` opacidad 0.5 |
| Botón secundario | `#12264E` (dark) / `#E2E8F0` (light) | `#1E3A6E` / `#E5E7EB` | — | igual primario |
| Botón grabar (64 px circular) | `#D4AF37` | `#B8860B` | — | — |
| Botón detener | `#EF4444` | `#DC2626` | — | — |
| VU meter | pista `#1E293B`, relleno `#D4AF37` | — | — | — |
| Recorte de nivel | relleno `#EF4444` + etiqueta "RECORTE" | — | — | — |
| Micro bajo | relleno ámbar + etiqueta "Bajo" | — | — | — |

**Transiciones:** 200 ms ease-out en todos los cambios de estado (pulso del botón grabar 450 ms,
toast: desliza + pulso + fade).

## 6. Feedback

- **Transcribiendo:** resaltado dorado en vivo en el área de transcripción + barra de progreso
  dorada + ticker de segundos + estimación por chunk (media móvil).
- **Éxito:** toast verde `[OK] Transcripción completada` + insignia **"Revisado por IA"**.
- **Error:** toast rojo con botón **"Reintentar"**.
- **Grabación lista:** toast verde.

## 7. Atajos de teclado

| Atajo | Acción |
|---|---|
| `Espacio` | Play/pausa de la grabación seleccionada |
| `Ctrl + R` | Nueva grabación |
| `Ctrl + S` | Guardar proyecto (aviso) |
| `Ctrl + E` | Exportar PDF |
| `F1` / `?` | Guía rápida |

Los atajos se ignoran cuando el foco está en un campo de texto o entrada.

## 8. Accesibilidad

- Contraste mínimo 4.5:1.
- Área táctil ≥ 44×44 dp en controles primarios.
- Foco visible (dorado) y navegación por teclado (tab order lógico).
- Modo oscuro/claro persistente (`config["theme"]`) con remapeo de superficies en vivo.
- Alternativas textuales (iconos con etiqueta) en botones de icono.

## 9. Modo oscuro

Oscuro: fondo `#0A1F44`, tarjetas `#12264E`, texto `#E8EDF7`. Claro: fondo `#F5F7FA`, tarjetas
`#FFFFFF`, texto `#1A202C`. El dorado se oscurece a `#B8860B` en claro para mantener contraste.
El header permanece azul marino en ambos modos.
