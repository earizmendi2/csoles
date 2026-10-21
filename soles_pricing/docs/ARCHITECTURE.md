# Motor e integración

## Selección determinista

Hay dos etapas independientes. Cada una selecciona **una** regla ganadora; no se acumulan todas las coincidencias:

1. **Base:** precio nativo efectivo, lista del producto, fijo, costo/margen o costo/recargo; después aplica `discount_pct` de esa regla.
2. **Beneficio:** toma exclusivamente `discount_pct` y piso de margen de la regla ganadora. Sirve para beneficios generales, del segmento o del cliente sobre la base seleccionada. Los campos de método/precio de esta etapa no intervienen y se ocultan en la pantalla.

Orden de desempate: menor prioridad `sequence`; a igualdad, cliente antes de segmento antes de general; después SKU, familia+marca, marca, familia, sin criterio; mayor volumen mínimo; finalmente ID menor. La prioridad explícita puede cambiar cualquier preferencia anterior. Dos reglas idénticas no suman porcentajes. La familia incluye sus descendientes; todos los criterios de una regla se intersectan. SKU se identifica por variante de producto, no comparando texto de referencia interna.

Volumen por línea, convertido sin redondear a la UdM base del producto; límites mínimo/máximo inclusivos, máximo cero significa ilimitado. No se agrega volumen de varias líneas ni del histórico. Vigencias de fecha inclusivas y dentro de la compañía de la regla. El contacto comercial determina el segmento y la coincidencia por cliente; una dirección hija utiliza las condiciones de su empresa matriz. Segmentos archivados no habilitan reglas de segmento.

La fecha de evaluación pertenece a la cotización, inicia en la fecha del servidor y no se cambia al confirmar aunque Odoo actualice `date_order`. Un vendedor puede actualizarla al día actual; fechas históricas/futuras requieren Administrar precios. El simulador sí permite evaluar cualquier fecha. Una oferta vigente conserva la fecha de valoración original; la fecha de vencimiento de la cotización se comprueba al confirmar.

## Fórmulas, monedas e impuestos

Sean `B` la base después de su descuento, `b` el beneficio y `e` el adicional manual, expresados en puntos porcentuales:

- Sumados: `P = B × (1 − (b + e)/100)`.
- Sucesivos: `P = B × (1 − b/100) × (1 − e/100)`.
- Margen sobre venta: `(P − C)/P × 100`.
- Costo con margen: `B = C/(1 − m/100)`; exige `0 ≤ m < 100`.
- Costo con recargo: `B = C × (1 + r/100)`.

Los porcentajes son datos editables; los números 0 y 100 representan los límites matemáticos, no políticas comerciales. No se permite NaN ni infinito. El piso efectivo es el mayor entre compañía, regla base y beneficio. La facultad de descuento puede exigir un piso aún mayor. Sin facultad explícita el adicional autorizado es cero. Una facultad de aprobación solo puede exceptuar el piso si `override_floor` está activado y siempre respeta su propio margen mínimo no negativo. Precios cero y costos faltantes (cuando se exige costo positivo) no son excepciones autorizables.

Ejemplo del hilo: B=1350, b=2, vendedor e≤3. Modalidad sumada: preferente=1323; mínimo=1282.50. P solicitado=1250 implica adicional efectivo=5.407407…% y margen de 8% con C=1150. Por ello requiere aprobación. En modalidad sucesiva, mínimo=1283.31 y adicional solicitado≈5.51776%. Los ejemplos solo existen en pruebas/documentación.

Costo comercial: base+flete+otros, por producto/compañía, moneda y vigencia. No se admiten vigencias superpuestas activas. En ausencia de registro se usa `standard_price` de esa compañía; un registro explícito cero no se reemplaza silenciosamente. Se convierte moneda sin redondeo intermedio con el tipo de cambio nativo de Odoo en la fecha de evaluación y luego la UdM. Precio fijo se expresa sin impuestos por UdM base del producto, en la moneda del registro.

Listas nativas y precio del producto usan sus APIs de Odoo 18, incluida su base de impuestos y contexto de atributos sin variante. El motor compara precios **sin impuestos**. Al escribir `price_unit` se reconstruye la parte de impuestos incluidos; Odoo sigue calculando impuestos/subtotales/totales, factura y moneda. Las tasas, redondeos y posiciones fiscales son las de Odoo; no hay IVA ni MXN fijo en el motor. El descuento nativo no se duplica cuando Soles fija un precio preferente: el cálculo inicial y el recálculo lo ponen en cero.

## Facultades

Facultad = operación (descontar/aprobar) + usuario o grupo + criterios de alcance, producto, volumen, vigencia, compañía. Gana menor prioridad; a igualdad gana usuario específico, luego los desempates de reglas. No se escoge automáticamente el porcentaje más alto entre roles ni se suman capacidades. Un rol nuevo puede ser cualquier `res.groups`, sin modificar Python.

El sujeto de descuento es **el vendedor asignado a la cotización** (`user_id`), incluso cuando otro gerente la edita o el cliente la confirma por portal. Cambiar vendedor invalida las aprobaciones. El sujeto de aprobación es el usuario que pulsa Aprobar; ambos permisos son independientes. Sin autoaprobación, ni solicitante ni vendedor asignado pueden aprobar esa excepción.

## Autorización y concurrencia

Estados: pendiente → aprobada/rechazada/invalidada; aprobada → consumida/invalidada. Precio autorizado = neto exacto por unidad de la línea, dentro del contexto completo de la oferta. La huella SHA-256 incluye toda la cotización, productos, UdM, cantidades, descuentos, impuestos, cliente, vendedor, moneda, lista, fechas comerciales, política, evaluación, costos y versiones seleccionadas. No se puede mover la autorización a otra línea/cotización. No se copian autorizaciones ni marcas de anticipo.

Cambios en precio, cantidad, producto, impuestos, UdM, contactos, lista, compañía, fecha, vencimiento, vendedor, posición fiscal o término de pago invalidan todas las solicitudes activas de la cotización. Reglas, facultades y costos invalidan las de su compañía; cambios de bases nativas protegidas invalidan las de compañías activas de manera conservadora. Aunque el valor se restaure, el estado no vuelve a aprobado. Cambios externos adicionales se detectan al comparar huella y capacidad vigente del aprobador. `Válida actualmente` refleja esa comparación; Verificar vigencia materializa invalidaciones externas/expiradas.

El paso a `sale` se controla en `sale.order.write`, además del flujo normal: cubre confirmación nativa y RPC directo. Primero se bloquea la fila de la orden con `FOR UPDATE`, luego se evalúan todas las líneas y se consumen autorizaciones antes de la escritura final dentro de la misma transacción. Una excepción revierte todos los consumos. Mutaciones de líneas y aprobación bloquean la misma orden. Las colisiones de transacción se resuelven mediante el manejo normal de serialización/reintento de Odoo/PostgreSQL. No hay bandera booleana de contexto que omita el control.

Los anticipos nativos usan un token Python interno de identidad, imposible de suministrar mediante JSON/RPC, y una marca protegida. Solo el flujo privado del asistente nativo puede crear esas líneas con cantidad ordenada cero sobre pedidos confirmados. No se consideran rebajas comerciales. Una línea marcada únicamente `is_downpayment` por un cliente RPC no obtiene esa excepción.

## Archivos

`configuration.py`: políticas, segmentos, marcas, reglas, facultades, costos y protección nativa. `engine.py`: motor compartido. `math.py`: fórmulas puras. `sale.py`: campos, valoración, invalidación y confirmación. `approval.py`: máquina de estados y facultad del aprobador. `wizard/simulator.py`: simulador, política y puente para anticipos. `security/`: ACL y reglas. `views/`: interfaz nativa. `tests/`: pruebas transaccionales. `tools/`: conversor offline de exportaciones del HTML.
