# Soles - Gestión de Tesorería (Odoo 18)

Módulo V1 para gestionar solicitudes de pago sin modificar todavía la lógica contable de `account.payment`.

## Funcionalidades

- Solicitudes de pago con folio `PAY/YYYY/00000`.
- Origen por aprobación o extraordinario.
- Vinculación opcional con `approval.request`.
- Configuración de categorías de aprobación habilitadas.
- Control de monto aprobado vs. solicitudes de pago no canceladas.
- Factura PDF, XML CFDI y documentos adicionales.
- Estados: Borrador, Por validar, Listo para programar, Programado, Por pagar, Pagado, Cerrado, Devuelto y Cancelado.
- Calendario de pagos.
- Alertas por actividades de Odoo.
- Pagos recurrentes, solo alerta o generación automática de solicitud en borrador.
- Equipos y responsables de Tesorería.
- Permisos para Solicitante, Tesorería, Responsable de Tesorería y Administración y Finanzas.

## Instalación

1. Copiar la carpeta `soles_treasury` a una ruta incluida en `addons_path`.
2. Reiniciar Odoo.
3. Actualizar la lista de aplicaciones.
4. Instalar **Soles - Gestión de Tesorería**.
5. Asignar grupos a los usuarios.
6. Crear un Equipo de Tesorería.
7. En Tesorería > Configuración > Ajustes, crear la configuración de la compañía y seleccionar los tipos de aprobación permitidos.

## Importante

Esta V1 **no crea pagos contables (`account.payment`)**. El botón “Marcar pagado” solo actualiza el registro administrativo. La integración con facturas de proveedor, pagos y conciliación se deja para una siguiente fase una vez validado el flujo operativo.

## Pruebas recomendadas

1. Aprobación autorizada -> Crear solicitud de pago.
2. Solicitud extraordinaria sin aprobación.
3. Dos solicitudes contra una misma aprobación sin exceder el monto autorizado.
4. Intento de exceder el monto autorizado.
5. Programar un pago y verificar el calendario.
6. Ejecutar manualmente el cron de alertas.
7. Crear pago recurrente con generación automática en borrador y ejecutar su cron.
