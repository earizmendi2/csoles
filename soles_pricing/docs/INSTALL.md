# Instalación y operación

## Requisitos

Odoo **18.0** con `sale_management`, Python/PostgreSQL compatibles con su despliegue y permiso para agregar módulos de servidor. Odoo.sh y servidor propio admiten este flujo; una cuenta sin addons Python requiere otro tipo de despliegue. No instalar como módulo de otra versión.

1. Respaldar base y filestore. Usar primero una copia de preproducción y bloquear correos/pagos externos.
2. Extraer `soles_pricing.zip` en un directorio del `addons_path`. El resultado debe ser `addons/soles_pricing/__manifest__.py`.
3. Reiniciar Odoo, actualizar lista de aplicaciones e instalar **Soles Pricing**. Alternativa:

```sh
odoo-bin -c /ruta/odoo.conf -d BASE_PRUEBAS -i soles_pricing --stop-after-init --without-demo=all
```

4. Asignar al responsable el grupo **Soles · Precios / Administrar precios** desde Ajustes → Usuarios. Incluye administración del catálogo, creación de contactos, consulta de costos y acceso a todas las cotizaciones; reservarlo a personal de confianza. No incluye permiso de aprobación ni un porcentaje de descuento.
5. Abrir **Precios Soles → Configuración → Política por compañía**. Aplica exclusivamente a la compañía activa. La política también se consulta en la ficha de compañía.
6. Crear/editar segmentos, marcas y costos; asignar segmento en la ficha del cliente comercial y marca en el producto. El segmento depende de compañía, la marca es compartida por catálogo. No asignar segmentos de otra compañía.
7. Crear reglas base y de beneficio. Crear facultades para roles o usuarios. Asignar a usuarios los roles vendedor, gerente o gerente especial, y por separado **Aprobar extraordinarios** cuando corresponda.
8. Revisar casos en el simulador; avanzar por el plan A/B/C/D. No activar C con facultades/costos sin revisar.

## Cotización diaria

En modo C/D, las nuevas líneas calculan el precio preferente Soles. La lista nativa queda como respaldo si no gana una regla base. Las cotizaciones existentes conservan sus precios hasta usar **Recalcular Soles**: reemplaza precios manuales, pone el descuento nativo en cero e invalida aprobaciones.

Mostrar las columnas opcionales **Precio preferente**, **Mínimo vendedor** y **Descuento adicional efectivo (%)**. Esta última es editable y usa la modalidad sumada/sucesiva configurada; también se permite editar directamente el precio unitario o el descuento nativo. Todos los caminos se validan por su precio neto real al confirmar. El descuento nativo de Odoo se aplica sobre `price_unit`; para sumar puntos sobre la base Soles usar la columna Soles.

Si se requiere excepción, guardar la cotización, capturar **Motivo de excepción** y pulsar **Solicitar** en la línea. El solicitante ve la autorización y el aprobador entra desde **Precios Soles → Autorizaciones**. El aprobador debe tener el grupo de aprobación y una facultad `Aprobar` vigente que cubra el descuento y el margen. Si desea rechazar, debe indicar el motivo. Varias líneas requieren sus respectivas autorizaciones; solicitarlas no invalida las otras líneas.

Al confirmar se revisa toda la cotización y se consumen todas las autorizaciones necesarias en la misma transacción. No se consumen por abrir, imprimir, simular ni intentar una confirmación fallida. Un cambio comercial posterior a la solicitud invalida las solicitudes pendientes/aprobadas de esa cotización, incluso si se restaura el valor original.

Una orden confirmada protege sus condiciones comerciales. Para modificarlas, cancelar/regresar a borrador y obtener nuevas autorizaciones. La autorización consumida no se reutiliza. Duplicar la cotización no copia autorizaciones. El historial impide eliminar la cotización con autorizaciones; una línea sí puede eliminarse en borrador y su autorización permanece sin línea, invalidada.

Configurar email del usuario como requiere el chatter nativo de Odoo. Las solicitudes y decisiones dejan mensajes internos; este módulo no envía avisos externos ni crea aprobadores automáticamente. El aprobador puede consultar la bandeja con filtro Pendientes.

## Simulador

Seleccionar compañía, cliente, producto, UdM, cantidad, lista nativa, posición fiscal, fecha y vendedor a evaluar. Opcionalmente capturar un precio neto sin impuestos. Muestra reglas ganadoras, precio preferente, mínimo y motivos. Solo usuarios con **Consultar costos y márgenes** ven esos importes. No escribe cotizaciones ni consume aprobaciones.

## Actualización y pruebas

```sh
odoo-bin -c /ruta/odoo.conf -d BASE_PRUEBAS -u soles_pricing --stop-after-init
odoo-bin -c /ruta/odoo.conf -d BASE_PRUEBAS -u soles_pricing \
  --test-enable --test-tags=/soles_pricing --stop-after-init --without-demo=all
```

Tras una actualización revisar cambios de permisos, ejecutar la batería y los escenarios de su base. En una instalación nueva los nombres de segmento se cargan una vez (`noupdate=1`), sin sobrescribir ediciones posteriores.
