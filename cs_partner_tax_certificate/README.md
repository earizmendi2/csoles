# Constancia SAT

Módulo para **Odoo 18** que permite crear y actualizar contactos a partir de la **Constancia de Situación Fiscal** del SAT en formato PDF.

**Autor:** Cusoft  
**Sitio web:** https://www.cusoft.mx 
**Soporte:** apps@cusoft.mx  
**Licencia:** LGPL-3  
**Versión:** 18.0.1.4.9  
**Dependencia Odoo:** `contacts`

## Descripción general

Reduce errores manuales al capturar datos fiscales mexicanos (RFC, nombre, domicilio, régimen fiscal y URL de verificación del SAT) directamente desde el PDF de la constancia. Incluye un asistente para actualizar contactos consultando la URL oficial almacenada en el contacto.

## Funcionalidades

- Importar clientes o proveedores desde el PDF (lista, kanban o ficha de contacto).
- Extraer RFC, razón social o nombre, domicilio fiscal, régimen(es) fiscal(es) y URL del código QR.
- Asistente **Actualizar SAT** con comparación de campos y consentimiento explícito antes de consultar el portal.
- Detección de RFC duplicado con opción de actualizar el contacto existente.
- Mensajes amigables cuando faltan dependencias Python o `libzbar0`.

Compatible con **Odoo 18 Community y Enterprise**. Si `l10n_mx_edi` está instalado, el régimen puede sincronizarse con `l10n_mx_edi_fiscal_regime`.

## Instalación

1. Copie la carpeta `cs_partner_tax_certificate/` en su ruta de addons.
2. Instale las dependencias Python (ver abajo).
3. En Linux, instale `libzbar0` para lectura de códigos QR.
4. Reinicie Odoo y actualice la lista de aplicaciones.
5. Instale **Constancia SAT**.

```bash
pip install -r requirements.txt
sudo apt install libzbar0   # Debian/Ubuntu
./odoo-bin -d NOMBRE_BD -u cs_partner_tax_certificate --stop-after-init
```

Si actualizas desde una versión anterior a **18.0.1.4.3** (modelos `cif.parser`, etc.),
usa siempre `-u cs_partner_tax_certificate` hasta la **18.0.1.4.4** o superior para aplicar
las migraciones de renombrado.

## Dependencias Python

| Paquete | Uso |
|---------|-----|
| `PyPDF2` | Lectura del texto del PDF |
| `PyMuPDF` (`fitz`) | Renderizado del PDF para el QR |
| `pyzbar` + `Pillow` | Decodificación del código QR |
| `beautifulsoup4` | Parseo del HTML del SAT |
| `requests`, `certifi`, `truststore` | Consulta HTTPS a siat.sat.gob.mx |

## Dependencias del sistema

- **Linux:** `libzbar0` (requerido para que pyzbar decodifique el QR; no hace falta el comando `zbarimg`).

## Uso paso a paso

1. **Contactos → Nuevo desde CSF** (lista o kanban) o botón **Importar CSF** en la ficha.
2. Suba el PDF de la Constancia de Situación Fiscal.
3. Revise y corrija los datos extraídos.
4. Confirme para crear el contacto o actualizar uno existente con el mismo RFC.
5. En contactos con URL SAT guardada, use **Actualizar SAT**, marque el consentimiento y consulte el portal.

## Consulta al SAT

- Solo se permiten URLs HTTPS del dominio **siat.sat.gob.mx**.
- El PDF no se envía a Cusoft; la petición sale del servidor Odoo hacia el SAT.
- Antes de cada consulta el usuario debe aceptar el aviso de consentimiento en el asistente.

## Privacidad

Los datos del contacto no se envían al SAT en la consulta en línea (petición GET a la URL de verificación). El procesamiento del PDF ocurre en el servidor donde corre Odoo.

## Problemas comunes

| Situación | Solución |
|-----------|----------|
| No se lee el QR | `pip install pymupdf pyzbar Pillow` y `sudo apt install libzbar0` |
| Error SSL al consultar SAT | Actualice el módulo; use `certifi` y `truststore` |
| SAT no responde | Reintente; verifique internet del servidor |
| PDF inválido | Use el PDF original del SAT, no escaneos corruptos |
| Sin datos en actualización SAT | La constancia puede haber expirado o el SAT cambió el HTML |

## Compatibilidad

- Odoo 18 Community y Enterprise.
- Módulo `contacts` obligatorio.
- Opcional: `l10n_mx_edi`, `base_address_extended`, `cs_cfdi_factura` (campos de domicilio extendidos).
- El tipo Cliente/Proveedor del asistente marca `customer_rank` / `supplier_rank` solo si está instalado **Contabilidad** (`account`); con solo Contactos el alta funciona igual sin esos campos.
- No instale junto con `cs_constancia_fiscal` (flujos similares).

## Soporte

- Web: https://www.cusoft.mx   
- Correo: apps@cusoft.mx

## Estructura

Modelos técnicos (prefijo `cs.partner.tax.certificate.*`):

| Modelo | Rol |
|--------|-----|
| `cs.partner.tax.certificate.parser` | Extracción de datos del PDF |
| `cs.partner.tax.certificate.sat.service` | Consulta al portal SAT |
| `cs.partner.tax.certificate.import.wizard` | Asistente de importación |
| `cs.partner.tax.certificate.update.wizard` | Asistente de actualización SAT |

```
cs_partner_tax_certificate/
├── models/              # Parser PDF, servicio SAT, res.partner
├── wizard/              # Importación y actualización
├── views/
├── static/description/  # Página Odoo Apps (index.html, imágenes)
├── migrations/
├── LICENSE
└── requirements.txt
```
