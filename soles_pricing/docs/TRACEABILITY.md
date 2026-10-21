# Origen y trazabilidad

Entrada inspeccionada: conversación `6ad39238-e1c0-83e8-890f-3069dda909e8`, título **Diseñar precios por cliente**, y el adjunto `Cotizador_Soles_reglas_descuento_cliente (1).html`. El inventario del proyecto no contenía un addon previo `soles_pricing`; los otros entregables disponibles trataban perfiles de acceso y documentación corporativa. No se editaron archivos de `sources/`.

Los mensajes de usuario recuperables pidieron reglas por vendedor/cliente/gerente/gerente especial, configuración sin porcentajes en código y autorización de un solo uso por precio específico; también proporcionaron el caso 1350/2%/3%/1250/1150/8%. Los mensajes históricos del asistente devolvieron referencias opacas de contenido, sin texto legible. Las decisiones no recuperables no se presumen: se definen y documentan en esta versión.

El HTML aporta 1,282 productos, 22 categorías y 58 marcas no vacías. Sus perfiles Gold/Platino/Vibranium tienen tasas en JavaScript; aquí solo se inicializan sus nombres editables. Contiene importación/exportación local JSON/CSV/Excel, búsqueda y selección por SKU, intersección categoría/marca, prioridad SKU > categoría+marca > marca > categoría y descuento adicional sumado sobre la lista. No contiene integración con Odoo, permisos de servidor ni autorizaciones.

| Requisito | Implementación / evidencia |
|---|---|
| Segmentos editables | `soles.pricing.segment`, `data/segments.xml`; sin porcentajes preconfigurados |
| Reglas generales/segmento/cliente | `soles.pricing.rule`, criterios comunes y precedencia documentada |
| Familia, marca, SKU, volumen, vigencia | Coincidencia por intersección; variantes Odoo; pruebas de alcances/filtros |
| Costo+margen, lista, fijo y nativo | Motor compartido; costo con margen sobre venta y opción recargo |
| Facultad por rol y usuario | `soles.pricing.authority`, operaciones separadas, prioridad editable |
| Vendedor/gerente/especial | Grupos iniciales independientes; facultades definidas en datos |
| Autorización por cotización/línea | `soles.pricing.approval`, huella de cotización, línea y precio exacto |
| Un solo uso e invalidación | Consumo atómico en transición a venta; pruebas de cambio/restauración/cancelación/copia |
| Aprobar distinto de descontar | Grupo de aprobación más regla `approve`; pruebas de separación y autoaprobación |
| Costos y pisos | Registros de costo comercial, respaldo estándar y pisos de compañía/regla/facultad |
| Interfaz y simulador | Vistas Odoo 18, menús, columnas, ficha de cliente/producto, vista previa y wizard |
| Moneda, UdM e impuestos | APIs nativas Odoo 18; pruebas de conversión, docena e impuestos incluidos/posición fiscal |
| Facturas y anticipos | Flujo nativo con excepción interna para anticipos; prueba de factura de anticipo |
| Seguridad | ACL, reglas de compañía/documento, guardas de servidor, campos de costo restringidos |
| Pruebas, documentación, migración | `tests/`, `docs/`, conversor offline y etapas A/B/C/D |

Referencias técnicas primarias consultadas:

- [Código oficial Odoo 18: sale.order.line](https://github.com/odoo/odoo/blob/18.0/addons/sale/models/sale_order_line.py).
- [Código oficial Odoo 18: sale.order](https://github.com/odoo/odoo/blob/18.0/addons/sale/models/sale_order.py).
- [Código oficial: impuestos](https://github.com/odoo/odoo/blob/18.0/addons/account/models/account_tax.py).
- [Código oficial: asistente de facturación](https://github.com/odoo/odoo/blob/18.0/addons/sale/wizard/sale_make_invoice_advance.py).
- [Documentación oficial Odoo 18: pruebas](https://www.odoo.com/documentation/18.0/developer/reference/backend/testing.html).

El HTML original, su SHA-256 y el inventario del catálogo se conservan como referencias en el paquete de fuentes; no se cargan como datos al instalar el addon.
