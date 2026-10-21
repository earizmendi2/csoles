# Seguridad y alcance comprobable

## Matriz de permisos

| Capacidad | Vendedor | Gerente / especial | Aprobador | Administrador de precios |
|---|---:|---:|---:|---:|
| Cotizar y simular | Sí | Sí | Sí | Sí |
| Ver todas las cotizaciones | Según ventas nativas | Sí | Sí | Sí |
| Solicitar excepción sobre una línea editable | Sí | Sí | Sí | Sí |
| Descontar un porcentaje | Solo facultad `discount` | Solo facultad `discount` | Solo facultad `discount` | Solo facultad `discount` |
| Aprobar | No | No, salvo grupo adicional | Grupo + facultad `approve` | No, salvo grupo adicional |
| Consultar costo comercial/margen Soles | Solo grupo adicional | Solo grupo adicional | Sí | Sí |
| Configurar reglas, costos, facultades y segmentos | No | No | No | Sí |
| Alterar estado/huella/importe aprobado por RPC | No | No | No | No |

Los grupos gerente y gerente especial identifican roles; no contienen porcentajes ni otorgan aprobación por sí mismos. Un usuario puede pertenecer a más de un rol; la prioridad de facultades decide cuál aplica. Permisos base de Odoo y superusuario continúan siendo frontera de confianza.

ACL sin permisos anónimos, reglas globales de compañía y reglas de autorización por vendedor asignado o acceso de todas las ventas. Los costos comerciales solo tienen ACL de lectura para Consultar costos. Sus campos en líneas, simulador y autorizaciones usan `groups` de servidor, no solo ocultación visual. Esto no modifica la visibilidad de `standard_price`, reportes contables o costos de otros addons: revisar permisos nativos de inventario/contabilidad en la base destino.

Las acciones revisan acceso al documento antes de usar `sudo` en los datos internos. Crear/editar autorizaciones por RPC está cerrado, excepto el motivo de decisión de un aprobador sobre una solicitud pendiente. El historial no puede eliminarse. Los contextos JSON como `skip_pricing` no omiten la validación. Los importes aprobados se obtienen del servidor, no del navegador. No hay rutas HTTP públicas, credenciales, llamadas a servicios externos ni ejecución de código dinámico en reglas.

Cuando hay compañías en comparación/control, crear o alterar productos/listas nativas y sus bases de valoración exige Administrar precios; modificar costo estándar/familia/UdM/base de precio también. Esto evita abaratar la referencia para eludir la facultad. Es una restricción global conservadora sobre catálogo compartido. Puede afectar tareas de inventario/compras que actualicen costo estándar con un usuario ordinario: probar esos flujos en preproducción y usar una cuenta de integración autorizada. No otorgar Administrar precios al vendedor para resolver un error de integración.

Monedas, tasas, impuestos, pertenencias a grupos y cuentas de integración se consideran configuración privilegiada de Odoo. Un administrador con `sudo`, acceso SQL o capacidad de editar el código puede modificar la base: esta extensión no intenta controlar a un administrador del servidor.

## Límites y pruebas pendientes en la base destino

Se implementa control sobre cotizaciones y pedidos `sale.order`, y las facturas/anticipos nativos conservan el flujo contable de Odoo. No controla precios editados directamente en facturas, POS, compras ni otro documento distinto de ventas.

El modo C/D exige cantidad y precio neto positivos para líneas comerciales ordinarias. Devoluciones con cantidades negativas en una cotización, productos combo con precio cero, regalos y descuentos globales mediante líneas negativas requieren una política/adaptador adicional antes de usarlos en control activo. Los anticipos creados por el asistente nativo sí tienen una excepción interna validada; marcar manualmente una línea como anticipo no la exime.

No se ha probado el navegador con todos los temas, Enterprise, Studio, módulos fiscales mexicanos, `sale_stock`, `sale_margin`, loyalty, ecommerce, POS, suscripciones, compras/valoración automática ni módulos de marca externos. El control al pasar a `sale` se alcanza también por APIs/portal, pero no se ejecutó un recorrido de portal, firma ni cobro online en esta entrega. El campo de marca nuevo es independiente: si ya existe un campo Studio/OCA, se debe mapear durante la migración. Los modelos nativos usan su propia política de redondeo; impuestos compuestos, cantidades fraccionarias extremas y tipos de cambio históricos deben contrastarse con casos reales.

Las pruebas automáticas verifican el servidor, sus vistas y transacciones en Odoo 18 Community local temporal. Esto no garantiza funcionamiento en la base productiva del cliente. No se hizo despliegue productivo, migración real de clientes ni prueba de carga. Revisar [VALIDATION.md](VALIDATION.md) para la evidencia exacta.
