# Configuración y operación

## Preparar la política

1. Asignar por separado Administrar precios, Preparar costos, Publicar políticas y Aprobar extraordinarios. Configurar facultades para los usuarios/grupos concretos.
2. Crear familias comerciales; elegir método por defecto, margen objetivo y pisos operativo/excepcional. No reorganizar categorías de inventario para hacer funcionar precios.
3. Revisar Gold/Platino/Vibranium o crear otros segmentos. Asignar el segmento al **contacto comercial principal** del cliente en la compañía activa.
4. Completar marca, familia y clasificación comercial de cada variante/producto. Los productos sin clasificación autorizada se bloquean en Control activo. Las clasificaciones iniciales no se asignan automáticamente al catálogo.
5. Si existe una marca de otro módulo, seleccionar su campo Many2one en Política de compañía y registrar en Marca Soles el modelo/ID del registro correspondiente. La marca Soles explícita del producto tiene preferencia. Sin correspondencia no se inventa una marca.
6. Preparar costos con moneda, vigencia y referencia documental. Enviar a revisión y publicar con el usuario publicador.
7. Preparar tipos de cambio comerciales necesarios, incluidos los requeridos por listas nativas; publicar después de revisar fuente y vigencia.
8. Crear reglas base generales/de segmento/de cliente, y beneficio adicional solo cuando corresponda. Habilitar la acumulación en política/familia expresamente; no se suman dos beneficios.
9. Revisar precedencias y restricciones de fabricante; preparar facultades `Descontar`/`Aprobar` y matriz de rutas con responsables suficientes.
10. Simular y pasar de Nativo a Comparación; después activar Control activo para el piloto validado.

## Niveles de clientes y menús

**Control de precios** abre directamente **Niveles de clientes**: una vista específica para asignar un nivel (Gold/Platino/Vibranium u otros editables) a contactos existentes y consultar sus reglas de precio. Administrar precios permite editar el nivel; los demás vendedores lo consultan. Los nuevos contactos se crean desde el flujo nativo de Odoo.

**Definir niveles** administra los nombres y reglas de cada nivel. **Reglas de precios**, **Facultades de descuento**, **Autorizaciones de precio** y **Simulador** reúnen los controles propios del módulo. Los publicadores acceden a documentos en revisión y los preparadores a costos; Configuración y Auditoría conservan los parámetros y su trazabilidad.

Las cotizaciones y pedidos se gestionan desde **Ventas**. La familia, marca y clasificación comercial se capturan en la ficha nativa de **Productos**; el nivel del cliente también está disponible en **Contactos**. El módulo agrega la política de precios a esos flujos existentes.

Los niveles no traen porcentajes fijos. Los roles vendedor, gerente y gerente especial tampoco. Asignar un rol sin facultad no concede descuentos extraordinarios. El grupo Publicar no concede facultad de aprobación.

## Publicar y cambiar condiciones

Crear un borrador, escribir la justificación y enviarlo a revisión. Un publicador revisa y publica. La versión queda identificada por revisión/usuario/fecha y su contenido no puede alterarse. Para modificarla, el editor crea **Nueva revisión**, cambia sus valores y vuelve a revisión/publicación. La nueva publicación retira la publicación anterior de esa serie; las cotizaciones existentes conservan la valoración anterior.

Una restricción futura con vigencia posterior también reemplaza la serie al publicarse: para conservar simultáneamente periodos independientes, crear documentos/series independientes con vigencias no superpuestas en costo/FX. No cerrar una publicación editándola; usar Retirar y publicar documentos revisados para los periodos requeridos.

## Cotizar y negociar

En Control activo, al agregar producto/cantidad/UdM se calcula el preferencial y se captura la valoración. La línea muestra base, preferencial, mínimo del vendedor, adicional efectivo, motivos, regla/revisión y estado de autorización. Quien tiene permiso de costos ve costo, versión y margen.

Editar precio o descuento nativo conserva la referencia preferencial para medir la negociación. Cambiar cliente/producto/cantidad/UdM/impuestos/lista u otras condiciones comerciales invalida autorizaciones y actualiza la valoración cuando corresponde. **Recalcular Soles** aplica la política publicada actual y elimina descuentos nativos previos: revisar el importe antes de confirmar.

Para una excepción: guardar cotización, capturar Motivo de excepción en la línea y pulsar Solicitar autorización. La solicitud muestra precio exacto, producto, cantidad/UdM, importes agregados, responsables y ruta. Cada línea fuera de facultad requiere su propia autorización, vinculada además a la huella de toda la cotización. Dividir descuentos entre líneas no evita el límite total.

El responsable asignado registra motivo y aprueba o rechaza. Si ninguno tiene facultad suficiente se informa **Sin responsable elegible**; un administrador revisa la matriz/facultades y el vendedor presenta una nueva solicitud. La autorización aprobada tiene vencimiento configurable y se consume al confirmar. No se reutiliza al duplicar, cancelar/regresar a borrador o modificar y restaurar condiciones. El cron marca vencidas; la confirmación comprueba el tiempo aunque el cron aún no haya corrido.

## Catálogo especial y simulador

Pendiente de revisión permite preparar el catálogo sin autorizar su venta. Precio válido autoriza venta interna/B2B según configuración. Cotización especial puede admitir referencia ausente únicamente si ambas opciones están habilitadas y exige aprobador con facultad expresa; el precio neto solicitado debe ser positivo y cumplir costos/pisos. La empresa debe fijar la referencia mínima para tratar $1 como marcador cuando corresponda.

El simulador selecciona cliente, SKU, cantidad/UdM, lista/moneda, fecha y vendedor; informa segmento, base, beneficio, preferencial, mínimo, versiones, motivos y ruta/responsables. Los editores/publicadores pueden previsualizar una regla borrador sin publicarla. La simulación considera una línea; la cotización vuelve a comprobar los límites acumulados de la oferta. No crea una aprobación ni un pedido.

En Nativo y Comparación Odoo conserva el cálculo nativo; Comparación registra hallazgos al confirmar. El simulador siempre permite consultar la política Soles. En Control activo, los faltantes de clasificación/costo/tipo de cambio no se resuelven con valores inventados.
