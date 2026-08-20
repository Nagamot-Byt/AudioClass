# Firma de Codigo — Plan de Implementacion

## Contexto

Windows SmartScreen bloquea ejecutables sin firmar. Para distribuir AudioClass
sin que el usuario vea la alerta "Windows protejo tu PC", necesitamos firmar
el .exe con un certificado de codigo reconocido.

---

## Estado Actual

- **Fase 1 (ahora)**: Self-signing en CI (certificado auto-generado)
- **Fase 2 (corto plazo)**: Aplicar a SignPath Foundation (gratis)
- **Fase 3 (opcional)**: Certificado OV/EV comercial si crece el proyecto

---

## Fase 1: Self-Signing en CI (implementado)

El pipeline de release genera un certificado auto-firmado y firma el exe Windows.
Esto NO elimina SmartScreen pero garantiza que el binario no fue modificado
post-build (integridad).

### Como funciona

1. `release.yml` ejecuta `New-SelfSignedCertificate` para crear un certificado
   temporal en el runner de GitHub Actions
2. Exporta el certificado a `.pfx`
3. Firma el exe con `signtool sign`
4. Borra el certificado al finalizar

### Limitaciones

- SmartScreen **SIGUE apareciendo** (certificado no es de CA confiable)
- El certificado expira y no es reutilizable entre runs
- Sirve para: verificacion de integridad, testing, distribucion interna

---

## Fase 2: SignPath Foundation (GRATIS — RECOMENDADO)

### Que es SignPath Foundation

SignPath Foundation es una organizacion sin fines de lucro que provee
certificados de firma de codigo **gratuitos** a proyectos de open source.
El certificado esta a nombre de "SignPath Foundation" y verifica que el
binario fue construido desde el repositorio fuente de forma automatizada.

**URL**: https://signpath.org

### Requisitos para aplicar

Tu proyecto debe cumplir **todos** estos criterios:

| Requisito | AudioClass | Estado |
|---|---|---|
| Licencia OSI-approved (MIT, GPL, etc.) | MIT | CUMPLE |
| Sin codigo propietario | Solo OSS | CUMPLE |
| Proyecto activamente mantenido | Commits recientes | CUMPLE |
| Release ya publicada | v9.1-final en GitHub | CUMPLE |
| Documentacion funcional | README.md + GUIA | CUMPLE |
| Sin malware/PUP | App de grabacion legítima | CUMPLE |
| Multi-factor auth en GitHub | Configurar | PENDIENTE |
| Code signing policy en repo | Crear | PENDIENTE |
| Roles asignados (Authors/Reviewers/Approvers) | Configurar | PENDIENTE |

### Pasos para aplicar

#### Paso 1: Preparar el repositorio

1. **Habilitar MFA** en tu cuenta de GitHub (Settings > Password > 2FA)
2. Crear `CODE_SIGNING_POLICY.md` en la raiz del repo (ver abajo)
3. Crear teams en GitHub:
   - `AudioClass/maintainers` (Authors + Reviewers)
   - `AudioClass/approvers` (Approvers — tu como owner)

#### Paso 2: Solicitar en SignPath.io

1. Ir a https://signpath.org y hacer clic en "Apply"
2. Crear cuenta en SignPath.io (gratis)
3. Crear una "Organization" vinculada a tu cuenta de GitHub
4. Seleccionar "SignPath Foundation" como certificate provider
5. Vincular el repositorio `Nagamot-Byt/AudioClass`
6. Configurar la integracion con GitHub Actions:
   - Descargar el artifact `signing-request.json` desde SignPath.io
   - Usar el action `SignPath/signpath-action` en el workflow

#### Paso 3: Integrar en release.yml (cuando se apruebe)

```yaml
# Paso de firma con SignPath (reemplaza el self-signing)
- name: Sign with SignPath
  uses: SignPath/signpath-action@v1
  with:
    ArtifactConfigurationId: 'default'
    PathToArtifact: '${{ github.workspace }}/AudioClass_v9.1_COMPLETA.zip'
    SignatureName: 'AudioClass'
    WaitForCompletion: 'true'
  env:
    SIGNPATH_API_TOKEN: ${{ secrets.SIGNPATH_API_TOKEN }}
```

#### Paso 4: Verificar

1. Hacer un push de tag (`v9.2`)
2. El pipeline firmarya el exe automaticamente
3. Verificar con `signtool verify /pa AudioClass.exe`

### Timeline estimado

- **Semana 1**: Preparar repo + enviar solicitud
- **Semana 2-3**: Revision de SignPath (pueden pedir cambios)
- **Semana 3-4**: Aprobacion + integracion en CI

---

## Fase 3: Certificado OV/EV Comercial (opcional)

Si el proyecto crece y necesita SmartScreen sin depender de SignPath:

| Proveedor | Tipo | Costo | Vigencia |
|---|---|---|---|
| Sectigo | OV | ~200 USD/ano | 1 ano |
| DigiCert | OV | ~250 USD/ano | 1 ano |
| GlobalSign | EV | ~400 USD/ano | 1-2 anos |

---

## Code Signing Policy (para SignPath)

Crear este archivo como `CODE_SIGNING_POLICY.md` en la raiz del repo:

```markdown
# Code Signing Policy — AudioClass

Free code signing provided by SignPath.io, certificate by SignPath Foundation.

## Team Roles

### Authors (Committers and Reviewers)
- Daniel Perez (owner): https://github.com/Nagamot-Byt

### Approvers
- Daniel Perez (owner): https://github.com/Nagamot-Byt

## Privacy Policy

This program will not transfer any information to other networked systems
unless specifically requested by the user or the person installing or
operating it.

See AVISO_DE_PRIVACIDAD.txt for full privacy policy.

## Build Process

All release binaries are built automatically by GitHub Actions from the
source code in this repository. The build process is fully transparent
and reproducible.
```

---

## Referencias

- SignPath Foundation: https://signpath.org
- SignPath Terms: https://signpath.org/terms
- SignPath Docs: https://docs.signpath.io
- GitHub MFA: https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa
