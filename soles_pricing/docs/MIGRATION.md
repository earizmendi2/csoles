# Migración de los precios heredados A/B/C/D

A/B/C/D son las **cuatro columnas de precio existentes** y pueden representar tanto referencias comerciales como facultades de vendedores. **No son fases de despliegue ni equivalen automáticamente a Gold/Platino/Vibranium.** No se conocen aquí los nombres técnicos de los campos reales de la base de Soles; deben inventariarse antes de ejecutar la migración.

## Inventario y separación de significados

Obtener de una copia de la base: modelo/campo técnico de cada columna, moneda, UdM, impuestos incluidos, compañía, mecanismo de actualización, productos afectados, listas nativas y otros módulos que escriben esos valores. Identificar si cada uso de A/B/C/D obedece al cliente, al vendedor, al canal, al volumen o a un acuerdo específico.

Exportar ventas/cotizaciones históricas con cliente, segmento real, vendedor/rol, SKU, familia comercial propuesta, marca, cantidad/UdM, precios A/B/C/D vigentes, precio cobrado, descuento, moneda/tipo de cambio, costo disponible y margen. Registrar la fuente y fecha de los costos; no tratar automáticamente AVCO como costo comercial aprobado.

Tabla de trabajo que debe completarse con evidencia:

| Legado | Campo técnico real | Significado probado | Destino posible | Validación necesaria |
|---|---|---|---|---|
| Precio A | Por inventariar | Por identificar | Referencia nativa/regla base/facultad, según evidencia | Moneda, impuesto, UdM, usuarios y vigencia |
| Precio B | Por inventariar | Por identificar | Regla de cliente/segmento o facultad | Identificar quién decide ese nivel |
| Precio C | Por inventariar | Por identificar | Acuerdo por familia/marca/SKU o facultad | Contrato y margen objetivo |
| Precio D | Por inventariar | Por identificar | Excepción publicada o facultad especial | Autoridad, piso y vencimiento |

Una columna puede alimentar varias políticas después de separar responsabilidades; varias columnas pueden resultar redundantes. No establecer equivalencias por orden alfabético. Mantener los campos heredados durante el periodo de comparación.

## Preparación de datos

- Depurar SKU duplicados, variantes/UdM incompatibles, marcas vacías o duplicadas y productos con referencias $0/$1.
- Crear familias comerciales sin cambiar categorías de inventario. Mapear las categorías del HTML a estas familias mediante una tabla explícita revisada.
- Confirmar segmentos reales de clientes y convenios individuales. Los perfiles del prototipo pueden reflejar facultades del vendedor y necesitan validación antes de asignarse como segmento.
- Documentar costos y tipos de cambio comerciales con periodos no superpuestos. Publicar solo después de revisión.
- Configurar precedencias, reglas base, beneficios autorizados, facultades de descuento/aprobación y matriz de responsables. Dejar tasas y usuarios determinados por la empresa.

## Comparación y activación

1. **Inventario:** respaldo verificable, exportación de políticas/precios y matriz de origen/destino aprobada.
2. **Preparación:** importar datos revisados en una copia, inicialmente en Nativo. Probar clasificación, monedas, costos, márgenes y responsables.
3. **Comparación:** ejecutar ambos criterios sobre la misma muestra y contexto. Medir precio antiguo/nuevo, diferencia absoluta/porcentual, margen, falta de costo/FX, reglas conflictivas y autorizaciones requeridas. Revisar por SKU/familia/marca/cliente/vendedor, no únicamente promedios.
4. **Piloto:** Control activo en la compañía/base de prueba acordada; validar con vendedores y aprobadores entregas, facturas y excepciones. No existe una activación parcial por usuario del modo de compañía.
5. **Corte:** ventana acordada, nuevo respaldo, configuración publicada, responsables asignados y tratamiento explícito de cotizaciones abiertas. Las cotizaciones sin valoración capturada requieren Recalcular Soles y revisión antes de confirmar.
6. **Seguimiento:** revisar diferencias, márgenes, solicitudes sin responsable, vencimientos y volumen de excepciones. Mantener A/B/C/D disponibles como consulta hasta cierre formal de migración.

La empresa debe aprobar umbrales de diferencia y márgenes, tasas por segmento/familia, contratos, responsables, vigencias, acumulación de beneficios, cambio de costos/FX y elegibilidad B2B. Esta entrega no inventa esos valores. Para reversión operativa volver a Nativo; para reversión de una actualización restaurar código/base/filestore del mismo respaldo.

## Conversión del JSON del HTML

`tools/convert_prototype.py` trabaja **sin conexión a Odoo**, a partir de la exportación JSON v1 o padrón con `clients` y un mapeo de IDs externos explícito. `tools/mapping.example.json` documenta el formato. Rechaza clientes/SKU/familias/marcas sin correspondencia, contactos duplicados y porcentajes inválidos.

```sh
python3 tools/convert_prototype.py exportacion.json mapping_revisado.json salida_nueva
```

Genera `partners.csv`, `rules.csv` y `audit.json` con hash de origen. Las reglas se crean en **borrador**, no publicadas. El CSV de contactos puede cambiar segmentos: revisarlo antes de importar. Los perfiles exigen segmento/familia/tasa explícitos; el conversor no deduce la tasa por el nombre ni interpreta A/B/C/D. Importar primero catálogo/marcas/familias/segmentos revisados, luego contactos/reglas. Probar en una copia y verificar las importaciones antes de publicar.

La herramienta no extrae compras ni migra automáticamente campos A/B/C/D de una base desconocida. El HTML no contiene los nombres técnicos, costos ni aprobadores reales necesarios para hacerlo con seguridad.
