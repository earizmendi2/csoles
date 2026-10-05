# Soles - Cancelación Automática de Pedidos v1.4

## Correcciones principales

1. Cada pedido se procesa dentro de un `SAVEPOINT`.
   - Si un pedido falla, se revierte únicamente ese pedido.
   - No quedan cancelaciones parciales.
   - El cron continúa con los demás candidatos.

2. El proceso de cancelación utiliza el contexto:

   ```python
   soles_autocancel=True
   ```

   Las acciones automatizadas comerciales que no deban ejecutarse durante una
   cancelación deben respetar este contexto.

3. Se ejecuta `flush_all()` dentro del contexto de autocancelación.
   Esto es importante en Odoo 18 porque algunos campos de `sale.order.line`
   se recomputan al final de la transacción y pueden disparar acciones
   automatizadas después de `_action_cancel()`.

4. Se eliminaron los `commit()` manuales. Odoo/`ir.cron` controla la
   transacción global.

5. El umbral usa `fields.Datetime.now() - timedelta(days=N)`, por lo que 3 días
   significan 72 horas reales.

6. La bitácora ahora distingue:
   - Cancelado
   - Simulación
   - Error

   y guarda el detalle del resultado.

## IMPORTANTE: acciones automatizadas de Soles

El módulo expone el contexto, pero las acciones automatizadas deben consultarlo.

### Acción de control MSRP / precio mínimo

Todo el código actual debe ejecutarse únicamente cuando NO sea autocancelación:

```python
if not env.context.get('soles_autocancel'):
    # código actual de validación de precio
```

### Acción de margen menor a cero

Igualmente:

```python
if not env.context.get('soles_autocancel'):
    # código actual de validación de margen
```

No se recomienda agregar OdooBot a las listas/grupos de exclusión, porque eso
excluiría a OdooBot de las reglas comerciales en otros procesos no relacionados.

## Actualización

1. Subir/reemplazar la carpeta `soles_sale_autocancel` en el repositorio.
2. Actualizar Apps List si aplica.
3. Actualizar el módulo **Soles - Cancelación Automática de Pedidos**.
4. Modificar las dos acciones automatizadas para respetar
   `env.context.get('soles_autocancel')`.
5. Probar primero en staging con un pedido candidato.
6. Revisar **Ventas > Configuración > Historial de Cancelaciones Automáticas**.

## Cron

No es necesario recrear el cron existente. El registro actual puede conservar:

- Usuario planificador: OdooBot
- Intervalo: 1 día
- Código: `model._cron_autocancel_ordenes()`
