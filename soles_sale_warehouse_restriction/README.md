# Soles - Restricción de Almacenes en Ventas

Módulo para Odoo 18 que limita los almacenes desde los que cada vendedor puede operar órdenes de venta sin ocultar información global mediante reglas de registro.

## Objetivo

Evitar que un vendedor seleccione o confirme una cotización/pedido usando un almacén que no le corresponde, manteniendo la visibilidad de información que la organización decida conservar.

## Alcance

El control se aplica a `sale.order` y protege:

1. **Interfaz:** el campo `warehouse_id` solo muestra almacenes autorizados para el usuario actual.
2. **Creación:** una cotización creada por un usuario restringido no puede quedar en un almacén no autorizado.
3. **Cambio de almacén:** se bloquea el cambio hacia un almacén no autorizado.
4. **Confirmación:** el permiso se valida de nuevo en `_action_confirm()` antes de generar la operación logística.
5. **Importaciones/API:** las validaciones de backend también aplican fuera de la interfaz web.

El módulo **no utiliza Record Rules sobre `sale.order`**, por diseño. Esto evita ocultar cotizaciones, afectar reportes o generar efectos secundarios sobre CRM/Contabilidad. La restricción es operativa: controla desde qué almacén puede vender el usuario.

## Dependencia

- Odoo 18
- `sale_stock`

## Instalación

1. Copiar la carpeta `soles_sale_warehouse_restriction` al `addons_path` personalizado.
2. Reiniciar el servicio de Odoo.
3. Activar modo desarrollador.
4. Ir a **Apps > Actualizar lista de aplicaciones**.
5. Buscar **Soles - Restricción de Almacenes en Ventas**.
6. Instalar.

Por línea de comandos:

```bash
./odoo-bin -d NOMBRE_BD -i soles_sale_warehouse_restriction --stop-after-init
```

Para actualizar después de cambios:

```bash
./odoo-bin -d NOMBRE_BD -u soles_sale_warehouse_restriction --stop-after-init
```

## Configuración por usuario

Ir a:

**Ajustes > Usuarios y compañías > Usuarios > [Usuario]**

En la sección de almacén aparecerán:

- **Restringir almacenes en ventas**
- **Almacenes de venta autorizados**

Ejemplo:

- Vendedor Guadalajara
  - Restringir almacenes en ventas: Sí
  - Almacenes autorizados: GDL90

- Vendedor Chihuahua
  - Restringir almacenes en ventas: Sí
  - Almacenes autorizados: almacén(es) de Chihuahua

- Dirección / Sistemas
  - Restricción desactivada, o bien grupo de excepción.

### Lista vacía

Si la restricción está activa y el usuario no tiene almacenes autorizados, no podrá vender desde ningún almacén. Esto puede usarse como bloqueo preventivo durante altas, cambios o bajas.

## Almacén predeterminado

Odoo 18 usa `res.users.property_warehouse_id` como almacén predeterminado del usuario. Este módulo respeta ese comportamiento.

Cuando la restricción está activa:

- Si el almacén predeterminado está permitido, se conserva.
- Si no está permitido, se usa el primer almacén autorizado de la compañía activa.
- Si no hay almacenes autorizados, no se devuelve un almacén predeterminado válido para venta.

## Grupos incluidos

### Gestionar restricciones de almacenes de venta

Autoriza la modificación de los campos del módulo **si el usuario ya tiene permisos de escritura sobre Usuarios**. El grupo no concede por sí mismo acceso administrativo a `res.users`.

### Omitir restricción de almacenes de venta

El usuario queda exento de la validación del módulo. Recomendado únicamente para Dirección, Sistemas o perfiles aprobados.

También quedan exentos automáticamente:

- Superusuario.
- Usuarios con `base.group_system`.
- Usuarios con `base.group_erp_manager`.

## Seguridad

La validación no depende del dominio de la vista. Aunque el usuario intente operar mediante importación, RPC/API o una personalización de interfaz, el backend vuelve a comprobar el almacén.

No se agregó una clave de contexto del tipo `skip_warehouse_restriction`, ya que una clave de contexto podría ser enviada desde RPC y convertirse en una vía de evasión. Las excepciones deben controlarse mediante permisos/grupos.

## Comportamiento multi-compañía

Solo pueden asignarse almacenes pertenecientes a compañías a las que el usuario tenga acceso. Existe una validación en backend para impedir configuraciones inconsistentes incluso mediante importación.

## Pruebas recomendadas antes de producción

1. Crear un vendedor de prueba con acceso únicamente a un almacén.
2. Crear una cotización y confirmar que solo aparece el almacén autorizado.
3. Confirmar una venta desde el almacén autorizado.
4. Intentar crear por importación/API una orden con otro almacén: debe bloquearse.
5. Intentar cambiar el almacén de una orden existente: debe bloquearse.
6. Verificar que Dirección/Sistemas pueda operar según el grupo de excepción.
7. Probar por compañía si se usa multi-compañía.

## Estrategia de despliegue sugerida en Soles

1. Instalar primero en staging.
2. Configurar 2-3 usuarios de una sola sucursal.
3. Probar cotización > confirmación > picking > entrega.
4. Revisar automatizaciones actuales que modifiquen `warehouse_id` o `user_id`.
5. Desplegar por sucursal.
6. Activar la restricción al resto de vendedores.
7. Mantener Dirección/Sistemas en excepción solo cuando exista una necesidad operativa real.

## Riesgos / consideraciones

- Una automatización ejecutada con el usuario del vendedor y que intente cambiar la orden a un almacén no autorizado será bloqueada; esto es intencional.
- Procesos ejecutados con `sudo()` operan como superusuario y, por definición de Odoo, pueden evadir controles de usuario. Deben revisarse los desarrollos personalizados que utilicen `sudo()` sobre ventas.
- El módulo controla ventas. No pretende restringir transferencias manuales independientes creadas directamente desde Inventario. Si se requiere ese alcance, debe añadirse un control específico sobre `stock.picking`.

## Archivos principales

- `models/res_users.py`: configuración y permisos por usuario.
- `models/sale_order.py`: validaciones de venta y dominio dinámico.
- `views/res_users_views.xml`: configuración en Usuarios.
- `views/sale_order_views.xml`: filtro del selector de almacén.
- `security/security.xml`: grupos administrativos y de excepción.
- `tests/test_sale_warehouse_restriction.py`: pruebas automáticas básicas.

## Versión

`18.0.1.0.0`
