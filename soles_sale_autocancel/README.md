# Soles - Cancelación Automática de Pedidos v1.5

## Novedades v1.5

1. **Botón manual** en la configuración: `Ejecutar cancelación ahora`.
2. El botón muestra **confirmación previa** antes de correr el proceso.
3. Nuevo grupo de seguridad: **Ejecutar cancelación manual**.
   - No concede permisos técnicos generales.
   - Los Gerentes de Ventas también pueden ejecutar el botón.
4. Cron y botón usan la misma lógica interna (`_run_autocancel_ordenes`).
5. El historial registra el **Origen** de cada intento:
   - Automático
   - Manual
6. La notificación al terminar el botón muestra candidatos, cancelados,
   simulaciones y errores.
7. Se conserva íntegramente la configuración de `dias_limite`: el valor se
   sigue tomando desde la configuración. N días equivalen a N x 24 horas.

## Seguridad de la cancelación

Cada pedido se procesa dentro de un `SAVEPOINT`. Si un pedido falla, se revierte
únicamente ese pedido y el proceso continúa con los demás.

La cancelación utiliza el contexto:

```python
soles_autocancel=True
```

Las acciones automatizadas comerciales que no deben ejecutarse durante una
cancelación deben respetarlo:

```python
if not env.context.get('soles_autocancel'):
    # validación comercial normal
```

Esto debe aplicarse, entre otras, a:

- Validación MSRP / precio mínimo.
- Validación de margen menor a cero.

No se recomienda agregar OdooBot a listas generales de exclusión.

## Modo simulación

El botón manual respeta `Modo simulación`. Si está activo:

- No cancela pedidos reales.
- Registra los candidatos en el historial.
- El origen se marca como `Manual`.

## Permiso para ejecución manual

En el usuario, asignar el grupo:

**Soles - Cancelación Automática > Ejecutar cancelación manual**

Los usuarios con `Gerente de Ventas` también pueden ejecutarlo.

## Actualización

1. Reemplazar la carpeta `soles_sale_autocancel` del repositorio.
2. Actualizar la lista de Apps si aplica.
3. Actualizar el módulo **Soles - Cancelación Automática de Pedidos**.
4. Verificar las acciones automatizadas comerciales para que respeten
   `env.context.get('soles_autocancel')`.
5. Probar primero en staging con **Modo simulación**.
6. Revisar el historial y confirmar que la columna **Origen** muestre `Manual`.
7. Desactivar modo simulación sólo después de validar los candidatos.

## Cron

El cron existente se conserva:

- Usuario planificador: OdooBot
- Intervalo: 1 día
- Código: `model._cron_autocancel_ordenes()`

El botón manual no modifica `nextcall`; ejecutar manualmente no cambia la
programación diaria del cron.
