# Migración A/B/C/D

Las letras se concretan aquí como etapas de transición. El historial recuperado no contenía una definición anterior verificable de A/B/C/D; no se atribuye esta definición a mensajes históricos no disponibles.

| Etapa | Modo | Trabajo y responsable | Criterio para avanzar | Reversión |
|---|---|---|---|---|
| A · Inventario y respaldo | `off` | Sistemas respalda DB/filestore; Comercial inventaría listas, descuentos, clientes, marcas, SKU, impuestos, UdM y costos; Finanzas aprueba definición de margen | Identificadores externos sin ambigüedades; origen de cada tasa y costo; matriz de facultades firmada; respaldo restaurado en prueba | Desinstalar solo en copia desechable o restaurar respaldo; en producción dejar off sin borrar historial |
| B · Comparación | `audit` | Configurar en copia aislada; importar, simular casos reales y comparar con HTML/listas; responsables revisan cada diferencia | Casos representativos conciliados; diferencias de moneda/impuesto/familias aceptadas; autorización de roles probada | Volver off; mantener reglas para revisión; no hay reescritura de precios por modo audit |
| C · Piloto controlado | `enforce` en compañía de pruebas/piloto | Capacitar vendedores/aprobadores; usar cotizaciones nuevas; probar facturación, anticipos y cancelación; monitorear bloqueos | Caso extraordinario completo y multi línea; revocación/invalidez; cierres de venta aceptados por Comercial y Finanzas | Volver audit/off por administrador; guardar bitácora de cambios; autorizaciones pendientes/aprobadas se invalidan al cambiar política |
| D · Operación | `enforce` | Activar compañía productiva aprobada, revisar reglas/costos y facultades con cadencia interna; Sistemas mantiene respaldo | Revisiones periódicas, ausencia de facultades huérfanas, datos y flujos conciliados | Mantener historial; restaurar respaldo solo ante daño de datos y con ventana coordinada |

El selector de política es **por compañía**, no por vendedor. Para un piloto parcial dentro de una misma compañía se usa una copia de base o una compañía de pruebas; esta versión no ofrece un interruptor de control por usuario. No activar C en toda una compañía suponiendo que solo afecta a un vendedor.

## Conversión de los archivos del prototipo

El HTML recibido contiene catálogo embebido del 15-oct-2026 y código de perfiles, pero sus clientes/reglas editados se guardan en el navegador o Excel elegido por el operador. Ese padrón no se recupera de un HTML estático. Se necesita exportar el JSON real de cada cliente o el padrón `clients` del navegador para migrar datos vivos. El módulo y conversor se entregan completos sin inventar clientes ni tasas autorizadas.

`tools/convert_prototype.py` lee `soles-client-discounts-v1` o un objeto con lista `clients`. No conecta a Odoo ni modifica el HTML. Requiere un mapa explícito de compañía, moneda, clientes, categorías, marcas, SKU y perfiles. Usar `mapping.example.json` como estructura, reemplazando todos los valores de ejemplo. Las tasas de los perfiles se proporcionan en el mapeo; el conversor nunca supone 5/7/9.

```sh
python3 soles_pricing/tools/convert_prototype.py \
  exportacion_cliente.json mapa_revisado.json carpeta_nueva_de_revision
```

Salida: `partners.csv`, `rules.csv`, `audit.json`. La carpeta debe ser nueva. El conversor rechaza clientes duplicados, porcentajes fuera de rango y referencias sin mapeo. Usa IDs externos estables; **los `productId`/`id` del catálogo HTML son índices locales, nunca IDs de Odoo**. Los CSV de reglas son para el modelo `soles.pricing.rule`; el CSV de clientes para `res.partner`, en la compañía activa correcta.

Orden de preparación/importación:

1. Exportar catálogo real de Odoo con IDs externos. Resolver SKU vacíos/duplicados, moneda y tax-inclusion del precio fuente.
2. Mapear categorías del HTML a familias Odoo y crear marcas/segmentos. No recrear productos a partir de índices ni nombres aproximados.
3. Importar asignaciones de marca y costos comerciales, con sus monedas/UdM/vigencias. Resolver solapamientos; documentar uso del costo estándar como respaldo.
4. Completar el mapa de clientes y perfiles; convertir el JSON, revisar los CSV y usar la prueba de importación nativa de Odoo.
5. Importar segmentos de cliente y reglas en la compañía correcta. Los IDs externos permiten volver a importar sin duplicar filas; una regla eliminada del JSON no se borra automáticamente en Odoo, debe archivarse expresamente.
6. Crear facultades de descuento y aprobación de forma separada. No convertir descuentos manuales de cotizaciones del HTML en derechos permanentes ni en autorizaciones aprobadas.
7. Ejecutar comparaciones y pruebas de aprobación/cancelación; avanzar por la tabla.

Los perfiles se convierten en reglas **base** de precio lista con descuento y familia explícita. Las reglas particulares del HTML también son base: la especificidad por SKU/marca/familia determina su ganador dentro del mismo alcance. Un nuevo beneficio adicional por cliente debe crearse como etapa **beneficio** y revisarse, porque el prototipo trataba las reglas particulares como reemplazo del perfil, no como acumulación automática.

Diferencias que requieren revisión al migrar: el prototipo restaba perfil/regla y adicional sobre la misma lista, sin moneda ni impuestos. La extensión distingue base y beneficio y permite modalidad sumada o sucesiva; además incluye subfamilias. En prioridades iguales, cliente gana a segmento antes que especificidad de producto; revisar cualquier excepción general que antes pretendiera desplazar reglas de cliente. Mantener las prioridades explicitas del importador iguales y revisar los ganadores en Simulador.

Cotizaciones en curso, aprobaciones extraordinarias anteriores y facultades no se importan automáticamente. Las cotizaciones existentes siguen con sus precios hasta recálculo explícito; después de activación todas las confirmaciones se controlan. Cada excepción debe solicitarse de nuevo en Odoo. Los CSV/JSON importados deben almacenarse con acceso restringido por contener condiciones comerciales.
