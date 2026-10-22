# Validación de la versión 1.1 consolidada

## Entorno y alcance

Pruebas reales sobre Odoo 18 Community, código oficial de la rama 18.0 disponible localmente, Python 3.12.14 y PostgreSQL 18.4. Bases temporales aisladas, sin datos productivos de Soles. Dependencias `sale_management` y `sale_stock`. Versión técnica del addon 18.0.1.1.2.

No se afirma que esté probado en la base productiva, Odoo Enterprise, Odoo.sh o una instalación con módulos personalizados/localización de Soles. La aceptación comercial de tasas, márgenes, contratos, costos, FX y responsables sigue pendiente de su configuración real.

## Casos ejecutados

La suite `tests/test_spec.py` contiene **70 casos funcionales**. Verifica el cálculo sucesivo, independencia del vendedor, prioridades configurables, publicación/revisiones inmutables, previsualización de borradores, conservación de valoración, costo independiente de AVCO, fuentes, superposición de costos, FX comercial y faltantes, límites monetarios acumulados, fabricantes, pisos operativos/absolutos, clasificación, cotización especial, invalidación, copia/cancelación, fraude por API, costos confidenciales, multicompañía, vencimiento, rechazo/cancelación/actividades, escalamiento, separación de funciones, formulario nativo, simulador, auditoría anterior/nueva, monedas/UdM/impuestos, referencia mínima por UdM activación sobre cotizaciones previas, mínimos combinados y protección de la identidad del negociador.

Incluye confirmación → reserva → entrega terminada → factura de entrega, con aprobación consumida una sola vez; y anticipo porcentual del asistente nativo, junto con rechazo de un anticipo falso por contexto público.

`tools/test_converter.py` contiene **6 pruebas sin Odoo** del mapeo explícito de importación, borradores, porcentajes inválidos, faltantes, duplicados e idempotencia del resultado.

La comprobación de concurrencia (`tools/check_concurrency.py`) crea una cotización aprobada de ejemplo en una base desechable, abre dos conexiones/transacciones independientes y fuerza la confirmación simultánea. Exige una sola confirmación, una aprobación consumida una vez y una entrega. La otra transacción debe ser rechazada por serialización o control comercial; una colisión ajena de seguidores de correo no cuenta como validación del control.

## Instalación limpia y actualización

Para la revisión 18.0.1.1.2 se comprobó la instalación limpia desde el ZIP extraído en `soles_pricing_levels_clean`, y la actualización desde 18.0.1.1.1 en `soles_pricing_11_zip_verified`. Las 70 pruebas se ejecutaron después de esa actualización, sin fallos ni errores. El ajuste final del nombre visible de niveles se validó mediante actualización de vistas e inspección visual. Los registros correspondientes se adjuntan en la entrega.

La interfaz abre directamente Niveles de clientes. Se verificó la retirada del tablero y de los accesos extra a cotizaciones/pedidos/catálogo, así como la disponibilidad de las pantallas nativas. El motor, la integración de ventas y las aprobaciones conservan los mismos archivos que en la versión validada anteriormente; no fue necesario repetir la prueba de concurrencia por este ajuste de interfaz.

También se ejecutó actualización desde una base temporal con versión 18.0.1.1.0 y cotización/solicitud de ejemplo. Se comprobó paso a Nativo, reglas/costos heredados en borrador y solicitud abierta invalidada. No hay conversión silenciosa de A/B/C/D ni publicación de datos sin revisión.

## Reproducción

En una instalación de prueba con las dependencias de Odoo, adaptando base/rutas/conexión:

```sh
odoo-bin -d soles_pricing_validacion --addons-path=/ruta/odoo/addons,/ruta/addons -i soles_pricing --without-demo=all --test-enable --test-tags=/soles_pricing --stop-after-init
python3 -m unittest discover -s soles_pricing/tools -p 'test_*.py'
```

El comprobador de concurrencia **crea y confirma datos, usuarios y políticas de ejemplo y hace commit**. Ejecutarlo exclusivamente en una base desechable cuyo nombre empiece por `soles_pricing_`:

```sh
odoo-bin shell -d soles_pricing_concurrencia --addons-path=/ruta/odoo/addons,/ruta/addons --no-http < soles_pricing/tools/check_concurrency.py
```

Las pruebas no publican datos reales ni representan una migración productiva. La inspección visual y los resultados finales de empaquetado se registran en el archivo de resultados de la entrega.

## Límites que requieren validación en Soles

Datos reales y volumen/concurrencia de producción; módulos de marca/producto personalizados; listas anidadas y acuerdos particulares reales; localización contable, facturas fiscales y configuración de correo; combinaciones no incluidas de descuentos/promociones/ecommerce/combo/recompensas. Esta entrega no implementa tienda, portal, adquisición automática de costos de compras ni un importador automático de campos A/B/C/D desconocidos.

Probar estas combinaciones en una copia antes del corte. Los resultados incluidos sustentan el alcance ejecutado, no una garantía de todos los escenarios posibles.
