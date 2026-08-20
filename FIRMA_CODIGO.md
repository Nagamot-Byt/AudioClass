# Firma de Codigo — Alternativas Gratuitas

## Contexto

Windows SmartScreen bloquea ejecutables sin firmar. Para distribuir AudioClass
sin que el usuario vea la alerta "Windows protejo tu PC", necesitamos firmar
el .exe con un certificado de codigo.

## Alternativas Evaluadas

### 1. SignPath Foundation (GRATIS para open source)
- **URL**: https://signpath.org
- **Costo**: Gratis para proyectos open source (solicitud manual)
- **Proceso**: Subes el exe a su plataforma, firman con su certificado EV
- **Ventaja**: Certificado EV real, SmartScreen no aparece
- **Desventaja**: Requiere aprobacion manual, proceso lento (1-2 semanas)
- **Veredicto**: MEJOR OPCIÓN GRATUITA

### 2. SSL.com OSS Signing (GRATIS)
- **URL**: https://ssl.com/certificates/open-source-code-signing
- **Costo**: Gratis para open source
- **Proceso**: Solicitas certificado, firmas con su herramienta
- **Ventaja**: Certificado valido
- **Desventaja**: Requiere validacion de identidad, proceso largo
- **Veredicto**: Buena alternativa a SignPath

### 3. Azure Trusted Signing (Tier gratuito)
- **URL**: https://azure.microsoft.com/products/trusted-signing
- **Costo**: Gratis para <100 firmas/mes
- **Proceso**: Configuras Azure, firmas via CLI
- **Ventaja**: Integracion con CI/CD, escalable
- **Desventaja**: Requiere cuenta Azure + configuracion compleja
- **Veredicto**: Para proyectos con CI/CD maduro

### 4. Self-Signing (GRATIS, limitado)
- **Comando**: `signtool sign /f cert.pfx /p password AudioClass.exe`
- **Costo**: Gratis
- **Ventaja**: Funciona inmediatamente
- **Desventaja**: SmartScreen SIGUE apareciendo (certificado no es de CA confiable)
- **Veredicto**: Solo para desarrollo/testing

### 5. Certificado OV/EV Comercial (~200-400 USD/ano)
- **Proveedores**: Sectigo, DigiCert, GlobalSign
- **Ventaja**: Certificado completo, SmartScreen desaparece
- **Desventaja**: Costo recurrente
- **Veredicto**: Para proyectos con presupuesto

## Recomendacion

**Fase 1 (ahora)**: Aplicar a SignPath Foundation (gratis). Mientras se aprueba,
usar self-signing en el CI para que el exe al menos tenga firma.

**Fase 2 (si crece)**: Certificado OV (~200 USD/ano) via Sectigo o DigiCert.

## Implementacion en CI

```yaml
# En release.yml, paso de firma (cuando tengas certificado)
- name: Firma de codigo
  env:
    SIGN_CERTIFICATE: ${{ secrets.CODE_SIGN_CERT }}
    SIGN_PASSWORD: ${{ secrets.CODE_SIGN_PASS }}
  run: |
    echo "$SIGN_CERTIFICATE" | base64 -d > cert.pfx
    signtool sign /f cert.pfx /p "$SIGN_PASSWORD" /tr http://timestamp.digicert.com /td sha256 "AudioClass COMPLETA v9.1.exe"
    rm cert.pfx
```
