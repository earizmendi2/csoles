# Soles - Gestión de Tesorería

Módulo para Odoo 18 orientado a la administración de solicitudes, programación y seguimiento de pagos.

## Funciones principales

- Solicitudes de pago con folio `PAY/YYYY/#####`.
- Origen opcional desde Aprobaciones o solicitud extraordinaria.
- Solo permite vincular aprobaciones completamente aprobadas y de tipos habilitados en configuración.
- Carga de factura PDF, XML CFDI y otros documentos.
- Flujo: Borrador → Por validar → Listo para programar → Programado → Por pagar hoy → Atrasado → Pagado → Cerrado.
- Actualización automática del estado por fecha mediante cron.
- Vista calendario y alertas por actividades de Odoo.
- Pagos recurrentes con alertas o generación de solicitud en borrador.
- Equipos de Tesorería, responsables y permisos.
- Configuración por equipo de días/fechas autorizadas para ejecutar pagos: día semanal, día del mes o fecha específica.
- Validación de la fecha programada contra el calendario del equipo de Tesorería.
- Chips de estado/origen con colores para facilitar identificación.
- Ícono propio de aplicación.

## Versión

`18.0.1.1.0`

### Cambios 1.1.0

- Corregido `tracking` no soportado sobre el campo HTML de descripción.
- Añadido estado automático `Atrasado`.
- `Por pagar hoy` se asigna solo cuando la fecha programada es la fecha actual.
- Aprobaciones vinculables únicamente cuando `request_status = approved`.
- Calendario operativo por equipo de Tesorería.
- Colores de badges en listados.
- Ícono de aplicación.

## Nota

Esta versión controla el proceso administrativo. No crea todavía registros `account.payment` ni contabiliza pagos automáticamente.
