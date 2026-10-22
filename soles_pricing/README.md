# Soles · Control de precios 1.1

Aplicación `soles_pricing` para Odoo 18. Versión técnica **18.0.1.1.2**: consolidación de la versión 1.1 con la especificación funcional aportada. Sustituye las entregas preliminares 18.0.1.0.0 y 18.0.1.1.0.

Centraliza familias comerciales, segmentos editables, acuerdos generales/de segmento/de cliente, costos comerciales publicados, tipo de cambio comercial, facultades de descuento, matriz de aprobadores y excepciones de un solo uso. Incluye ícono, asignación de niveles a clientes, reglas de precios, facultades, simulador y auditoría. La entrada abre directamente los niveles de clientes. Cotizaciones, pedidos, productos, entregas y facturas conservan sus pantallas nativas de Odoo.

El cliente determina el precio preferencial. El vendedor determina cuánto puede negociar. Aprobar, descontar, editar políticas, preparar costos y publicar son permisos independientes. No se instalan tasas de descuento, márgenes objetivos, aprobadores ni acuerdos reales.

## Cálculo

Una regla base ganadora determina precio nativo, referencia de producto, importe fijo, costo/margen o costo/recargo. Un único beneficio adicional puede aplicarse si la compañía/familia lo permite expresamente. El descuento del vendedor siempre es sucesivo sobre el preferencial.

Ejemplo de pruebas, **no configuración de producción**: base $1,350; beneficio 2% → $1,323; facultad del vendedor 3% → mínimo $1,283.31. Solicitar $1,250 representa 5.5178% adicional; con costo comercial de $1,150 deja 8% de margen sobre venta. Requiere una autorización cuyo responsable tenga facultad suficiente.

Las reglas, costos, tipos de cambio y restricciones de fabricante pasan por borrador → revisión → publicación. Una publicación es inmutable; un cambio requiere nueva revisión. Las cotizaciones conservan la valoración aplicada; publicar otra regla no reescribe su precio. **Recalcular Soles** es una acción explícita.

## Entrega y uso

- [Instalación y actualización](docs/INSTALL.md).
- [Operación y configuración](docs/WORKSPACE.md).
- [Arquitectura y fórmulas](docs/ARCHITECTURE.md).
- [Permisos y controles](docs/SECURITY.md).
- [Migración desde precios heredados A/B/C/D](docs/MIGRATION.md).
- [Pruebas ejecutadas y límites de validación](docs/VALIDATION.md).
- [Origen y cobertura de requisitos](docs/TRACEABILITY.md).

Depende de `sale_management` y `sale_stock`; utiliza entregas, facturación y anticipos nativos. No depende de Tesorería ni de Aprobaciones Enterprise. Inicia en **Nativo**. La instalación y las pruebas descritas corresponden a una base temporal real de Odoo 18 Community; la instalación particular de Soles requiere su propia prueba con copia de datos y módulos personalizados.

Autor: Rubén Castillo. Licencia LGPL-3.
