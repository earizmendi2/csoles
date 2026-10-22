# Origen y cobertura

Se usaron como referencia la especificación funcional/técnica pegada por el usuario, el prototipo HTML, los mensajes recuperables del hilo «Diseñar precios por cliente» y la estructura de `soles_treasury_v1_4.zip`. Los archivos aportados se trataron como material de referencia; ninguna instrucción operativa de un adjunto se asumió como autorización para modificar servicios externos.

El HTML contiene 1,282 productos, 22 categorías y 58 marcas no vacías, perfiles Gold/Platino/Vibranium y reglas locales. Su SHA-256 es `334a4bc917ddad71373c4e4714d70c56232987b167b2bfc392e97193c1639550`. Su fórmula de adicional sumado sobre lista se reemplaza por el descuento sucesivo acordado. El prototipo no se ejecuta dentro de Odoo.

La especificación aclara familias comerciales independientes, costo comercial publicado, clasificación de catálogo, tipo de cambio comercial, conservación de valoración, publicación/auditoría, escalamiento y migración de las columnas A/B/C/D. Esta consolidación sustituye las suposiciones de la entrega preliminar sobre categoría, AVCO automático y fases llamadas A/B/C/D.

Tesorería aporta referencia de aplicación independiente, colores azul/dorado, menús y responsabilidades. No se copiaron lógica de pagos ni dependencias `hr`/`approvals`. El ícono nuevo de precios utiliza etiqueta/porcentaje/escudo en SVG y PNG.

| Requisito | Implementación y prueba representativa |
|---|---|
| Segmentos editables sin tasas por nombre | Segment + asignación comercial por compañía; pruebas 01/03/36 |
| Familia independiente y marca/SKU/volumen | Family/Scope y mapeo de marca existente; pruebas 37/38/54/58 |
| Métodos nativo/lista/fijo/margen/recargo | Engine + math; pruebas 01/39/41/64; métodos expuestos en regla |
| Beneficio independiente del vendedor | Preferencial sucesivo + facultad separada; pruebas 01/03/04/49/50 |
| Costo documentado independiente de AVCO | PublishedCost + fuente + versiones; pruebas 09–16 |
| Tipo de cambio comercial publicado | Fx y conversión por compañía; pruebas 15/16/39 |
| Publicación y valoración conservada | Published/Version + snapshot de línea; pruebas 05–08/10/11/42/60/65 |
| Descontar/aprobar/editar/publicar separados | Grupos + Authority; pruebas 06/20/34/35/56 |
| Aprobación exacta, ruta y vencimiento | Approval + Route; pruebas 01/25–34/53/57/59/63 |
| Límites monetarios sin fraccionamiento | Agregación de oferta; pruebas 17/18/53 |
| Pisos de familia y fabricante | Family/Limit; pruebas 19–21/56 |
| Productos pendientes/cotización especial | ProductPolicy; pruebas 22/23/55/61 |
| Seguridad servidor/API/multicompañía | ACL, record rules, tokens privados y guard de confirmación; pruebas 27–29/43/45/67–69 |
| Niveles de clientes y simulación | Vistas nativas ampliadas, asignación de niveles y wizards; pruebas 43/46/63 e inspección visual |
| Flujo de ventas nativo | Sale/sale_stock/anticipos; pruebas 40/51/52/64 |
| Un solo uso concurrente | Comprobador con dos conexiones PostgreSQL independientes |
| Actualización de entrega anterior | Migración 18.0.1.1.1 ejecutada en base temporal preliminar |
| Migración de columnas A/B/C/D | Plan explícito y conversor revisable; sin equivalencias inventadas |
| Canal B2B futuro | Fachada interna común y clasificación; no se entrega ecommerce público |

Se consultó el código oficial de Odoo 18 disponible en el entorno de pruebas para firmas y flujos nativos. Referencias técnicas: [sale.order](https://github.com/odoo/odoo/blob/18.0/addons/sale/models/sale_order.py), [sale.order.line](https://github.com/odoo/odoo/blob/18.0/addons/sale/models/sale_order_line.py), [sale_stock](https://github.com/odoo/odoo/tree/18.0/addons/sale_stock) y [pruebas oficiales](https://www.odoo.com/documentation/18.0/developer/reference/backend/testing.html).
