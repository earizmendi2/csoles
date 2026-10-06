# Soles - Cancelación Automática de Pedidos v1.5.1

## Cambios de esta versión

- Se mantiene la lógica estable de v1.4: días configurables, exclusiones, modo simulación, `soles_autocancel=True`, `SAVEPOINT` por pedido y `flush_all()` controlado.
- Botón **Ejecutar cancelación ahora** en la configuración.
- Confirmación antes de ejecutar.
- El botón usa las mismas reglas y el mismo valor de `dias_limite` que el cron.
- Historial con columna **Origen**: Automático / Manual.
- Permisos totalmente independientes de Gerente de Ventas:
  - **Autocancelación: ejecutar manualmente**: permite abrir la configuración en modo lectura y ejecutar el botón.
  - **Autocancelación: administrar configuración**: permite editar la configuración e implica el permiso de ejecución manual.
- Los permisos aparecen en **Otros permisos adicionales** del perfil de usuario.

## Importante sobre acciones automatizadas comerciales

Las acciones de validación de precio/MSRP y margen deben iniciar su lógica con:

```python
if not env.context.get('soles_autocancel'):
    # lógica comercial existente
```

Esto evita que reglas de validación comercial bloqueen una cancelación técnica.

## Flujo recomendado de prueba

1. Actualizar el módulo en staging.
2. Asignar `Autocancelación: administrar configuración` a Sistemas.
3. Activar **Modo simulación**.
4. Ejecutar el botón manual.
5. Revisar el historial: `Origen = Manual`, `Resultado = Simulación`.
6. Desactivar simulación y probar un pedido controlado.


## Cambio v1.5.2

- El menú **Configuración** ya no depende del permiso de ejecución manual.
- Todo usuario interno con acceso a Ventas puede abrir la configuración en modo lectura.
- **Ejecutar cancelación ahora** sólo aparece con el permiso `Autocancelación: ejecutar manualmente`.
- La edición de la configuración sigue requiriendo `Autocancelación: administrar configuración`.
- La opción Configuración abre directamente el registro **Configuración General**.
- No existe ninguna dependencia con Gerente de Ventas.


## Permisos v1.5.3

En **Ajustes > Usuarios**, el perfil muestra la categoría **Soles - Cancelación Automática**:

- **Ejecutar cancelación manual**: puede ver la configuración y usar el botón manual; parámetros en sólo lectura.
- **Administrar autocancelación**: puede editar toda la configuración y también ejecutar manualmente.
- Los usuarios con permiso técnico de **Ajustes / Administración** reciben automáticamente **Administrar autocancelación** para evitar dejar el módulo sin administrador.

No existe dependencia con Gerente de Ventas ni con ningún rol comercial.
