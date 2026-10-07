# Soles - Gestión de Tesorería

Módulo para Odoo 18 orientado al control administrativo de solicitudes y programación de pagos.

## Versión 18.0.1.3.0

Autor: Rubén Castillo

### Funciones principales

- Solicitudes de pago vinculadas opcionalmente a Aprobaciones completamente aprobadas.
- Solicitudes extraordinarias independientes.
- Origen diferenciado para solicitudes generadas desde Pagos recurrentes.
- Factura PDF/XML, documentos y comprobante de pago.
- Calendario de pagos y estados automáticos: Programado, Por pagar hoy y Atrasado.
- Calendarios permitidos por equipo y excepción auditada para pagos fuera de calendario.
- Equipos de Tesorería, revisor predeterminado y responsable de ejecución.
- Alertas internas de Odoo mediante notificaciones y actividades.
- Notificaciones al solicitante, revisor y responsable durante el flujo.
- Correo al solicitante al confirmarse el pago.
- Pagos recurrentes y generación de solicitudes en borrador.

## Flujo

Borrador → Por validar → Listo para programar → Programado/Por pagar hoy/Atrasado → Pagado → Cerrado.

La versión actual no crea `account.payment`; el control contable permanece desacoplado para pruebas.
