# Arquitectura del motor

## Modelos y responsabilidades

| Modelo | Función |
|---|---|
| `soles.pricing.segment` | Nombres Gold/Platino/Vibranium iniciales y otros segmentos editables, por compañía |
| `soles.pricing.family` | Jerarquía comercial independiente de `product.category`, método y márgenes predeterminados |
| `soles.pricing.brand` | Marca propia o correspondencia explícita con un catálogo de marca existente |
| `soles.pricing.product.policy` | Tratamiento válido/pendiente/cotización especial; referencia mínima y elegibilidad futura B2B |
| `soles.pricing.rule` | Base o beneficio, alcance y condiciones de aplicación |
| `soles.pricing.cost` | Costo documentado por variante, moneda y vigencia; componentes base, flete y otros |
| `soles.pricing.fx` | Tipo comercial publicado, moneda de compañía por una unidad extranjera |
| `soles.pricing.limit` | Precio mínimo de fabricante; excepción posible solo si se declara expresamente |
| `soles.pricing.authority` | Facultad para descontar o aprobar, por usuario/grupo y condiciones |
| `soles.pricing.precedence` | Orden configurable de alcances, criterios y sujetos |
| `soles.pricing.route` | Destinatarios y escalamiento según alcance/importe del descuento de la oferta |
| `soles.pricing.approval` | Precio exacto, condiciones y responsables; aprobación y consumo único |
| `soles.pricing.version` | Copia inmutable del documento publicado, revisión, autor y justificación |
| `soles.pricing.audit` | Cambios de configuración con usuario, fecha, valores anteriores/nuevos |
| `soles.pricing.engine` | Motor común de simulación, cotización y futura consulta B2B |

## Selección y precedencia

Primero se filtran compañía, activo, estado publicado, alcance (general/segmento/cliente), familia y descendientes, marca, SKU, volumen normalizado a UdM base, moneda y fechas inclusivas. Los criterios de una misma regla se intersectan. La categoría nativa permanece como filtro de compatibilidad, no como sustituto de familia comercial.

El orden es: prioridad explícita del documento (menor primero), primera fila coincidente de la matriz de precedencias, mayor cantidad mínima y finalmente menor ID como desempate determinista. Una condición sin fila de matriz queda detrás de las que sí coinciden. No se acumulan varias reglas base ni varios beneficios. Los porcentajes nunca se eligen por el nombre Gold/Platino/Vibranium ni por un rol escrito en código.

La matriz inicial editable prioriza condiciones de cliente, luego segmento, luego general; dentro de cada alcance, SKU, familia+marca, marca y familia. Incluye compatibilidad de categoría. Para facultades propone usuario antes de rol. Esta política se almacena como datos de Odoo y puede modificarse; una prioridad explícita permite una excepción deliberada.

## Fórmulas y unidades

- Margen sobre venta: `(precio_neto - costo_comercial) / precio_neto × 100`.
- Costo + margen: `costo / (1 - margen_objetivo/100)`.
- Costo + recargo: `costo × (1 + recargo/100)`.
- Preferencial: `base × (1 - beneficio/100)`.
- Mínimo por porcentaje del vendedor: `preferencial × (1 - facultad/100)`.
- Adicional efectivo: `(1 - precio_solicitado/preferencial) × 100` cuando el preferencial es positivo.

Los valores del motor son unitarios **sin impuestos** en moneda/UdM de cotización. Se usan los servicios nativos de Odoo para UdM, posición fiscal e impuestos incluidos/excluidos. Los campos `price_unit` y `discount` continúan siendo los campos nativos; la integración invierte la base de impuestos incluidos al presentar/aplicar el importe.

La comparación monetaria respeta el redondeo de la moneda; márgenes y cálculos intermedios conservan precisión. La referencia mínima de clasificación se valida por UdM base y moneda de compañía, para evitar que cambiar a docena legitime un precio marcador $1.

## Costo y tipo de cambio

Solo se evalúan costos comerciales publicados, documentados y vigentes. No se usa `standard_price` como sustituto automático. El botón Capturar costo contable toma una **fotografía explícita** en un borrador; necesita revisión y publicación. Compras/reposición/importación son fuentes documentales seleccionables, no sincronizadores automáticos de compras.

El costo aplicable es base+flete+otros. Se impide superposición de costos publicados por compañía/variante. El tipo de cambio comercial también impide superposición. La conversión cruzada pasa por la moneda de compañía. Si falta una tasa necesaria en modo comercial, la evaluación falla sin sustituirla por el tipo contable. La política puede elegir explícitamente tipo contable nativo; esa alternativa no cambia los tipos de Odoo.

Una cotización captura base, beneficio, preferencial, método, segmento, reglas/versiones, costo y conversión. Nuevas publicaciones no modifican su precio. La política de compañía permite reevaluar el costo comercial actual al confirmar o conservar el capturado. La identidad del negociador se registra en servidor al crear/modificar condiciones de la línea; cambiar el vendedor asignado no suple su facultad. Facultades, clasificación, pisos y permisos vigentes se vuelven a validar. Publicar/desactivar políticas o cambiar configuración invalida autorizaciones abiertas conservadoramente, incluso si el cambio pudiera mejorar el precio.

## Aprobación transaccional

La huella incluye la cotización completa y todas sus líneas, precios/descuentos/impuestos, cantidad/UdM, cliente, vendedor, compañía, moneda/lista, posición fiscal, condiciones de pago/vigencia y marcadores de políticas. Cambiar y restaurar condiciones no rehabilita una autorización invalidada.

La matriz de rutas examina candidatos en orden y omite responsables sin facultad suficiente. El aprobador debe estar activo, pertenecer a la compañía, tener grupo de aprobación y facultad `approve` compatible; se revisan porcentaje, margen, piso absoluto, importe neto y descuento monetario agregado de toda la oferta. El descuento monetario para estos límites es el **adicional negociado sobre el preferencial**, sumado en moneda de compañía.

Se admite precio bajo el piso operativo solo si la facultad lo permite; el piso excepcional absoluto de familia no se exceptúa. Un mínimo de fabricante solo puede exceptuarse si el documento y el aprobador lo permiten ambos. La autoaprobación está desactivada inicialmente y tiene política explícita.

El pedido se bloquea por fila de PostgreSQL; la transición real a venta verifica las aprobaciones y las consume en la misma transacción. Se protege también una escritura directa de estado por API. Si falla la operación, se revierte el consumo. Una confirmación concurrente con una fotografía anterior puede ser reintentada por la infraestructura nativa de Odoo; no genera un segundo consumo.

## Integración y canal futuro

Se conserva el flujo nativo de entregas/facturas/anticipos. Los anticipos creados por el asistente nativo llevan una marca interna imposible de establecer mediante contexto JSON público; no son una vía para eximir líneas comerciales. No se reevalúan descuentos al entregar/facturar ni se vincula el costo comercial a movimientos AVCO.

`get_customer_price(partner_id, product_id, quantity, pricelist_id)` es una fachada para usuarios internos de Ventas con ACL y compañía comprobadas. Devuelve una selección de datos; costos/márgenes solo con su grupo. No es una ruta pública ni un portal/ecommerce. Un adaptador B2B futuro deberá autenticar el cliente, fijar su identidad, aplicar `allow_b2b` y usar este motor, sin exponer costos o facultades internas.
