# Instalación y actualización

## Requisitos

Odoo 18 con sus dependencias oficiales y PostgreSQL compatible. El servidor debe poder instalar `sale_management` y `sale_stock` (y sus dependencias nativas). No requiere librerías Python adicionales al entorno de Odoo ni compilación externa del frontend.

La entrega ZIP contiene una sola carpeta `soles_pricing/`, con código Python/XML, ícono, seguridad, migraciones, documentación y pruebas. No contiene Odoo, PostgreSQL, una base de datos ni credenciales.

## Instalación nueva

1. Respaldar base y filestore y preparar una copia de validación.
2. Descomprimir el ZIP dentro de una ruta de addons del servidor. Debe existir `addons/soles_pricing/__manifest__.py`, sin otra carpeta intermedia.
3. Incluir la ruta padre en `addons_path`, reiniciar Odoo, actualizar la lista de aplicaciones e instalar **Soles - Control de precios**.
4. Asignar los grupos de Soles a usuarios concretos. Un administrador técnico no recibe automáticamente una facultad comercial de descuento/aprobación.
5. Abrir **Control de precios → Niveles de clientes** y mantener **Nativo** mientras se prepara la política.
6. Configurar familias, segmentos, clasificación del catálogo, marcas, precedencias, facultades, rutas, costos y monedas. Publicar documentos revisados.
7. Simular clientes y productos representativos. Ejecutar comparación y después el piloto con control activo según MIGRATION.md.

Instalación desde terminal, adaptando rutas y conexión:

```sh
odoo-bin -d BASE_VALIDACION --addons-path=/ruta/odoo/addons,/ruta/addons -i soles_pricing --without-demo=all --stop-after-init
```

## Actualización desde una entrega preliminar

Reemplazar la carpeta completa y actualizar el módulo, nunca instalarlo con otro nombre:

```sh
odoo-bin -d BASE_VALIDACION --addons-path=/ruta/odoo/addons,/ruta/addons -u soles_pricing --stop-after-init
```

La migración 18.0.1.1.1 deja las compañías en **Nativo**, normaliza la modalidad sucesiva, conserva reglas/costos anteriores como borradores y da a cada documento su propia serie de revisión. Invalida autorizaciones pendientes/aprobadas del motor preliminar. Conserva cotizaciones, importes nativos, clientes, facultades e historial consumido; completa compañía/moneda históricas y contador consumido cuando corresponde.

No publica costos sin fuente ni asigna familias/clasificaciones automáticamente. Requiere revisión comercial antes de volver a activar el control. Las cotizaciones nacidas en Nativo o antes de la consolidación deben usar **Recalcular Soles** y revisar su importe antes de confirmarse en Control activo; no se les inventa una valoración histórica.

Si la actualización falla, restaurar **base y filestore completos**, junto con la carpeta anterior. Cambiar solo el código no revierte cambios de esquema. La desinstalación elimina modelos/configuración propios conforme al ORM; no constituye un procedimiento de reversión de política comercial. Preferir Nativo para detener el control mientras se investiga.

## Compañías adicionales

Los segmentos de ejemplo, clasificaciones y matriz inicial pertenecen a la compañía principal. Crear/configurar equivalentes y la matriz de precedencia para cada compañía adicional; no hay tasas ni rutas globales asumidas. Seleccionar la compañía activa antes de importar o simular. Las marcas pueden compartirse entre compañías; sus acuerdos y costos siempre pertenecen a una compañía.

## Ajuste de interfaz 18.0.1.1.2

La actualización desde 18.0.1.1.1 cambia la entrada a Niveles de clientes y retira el tablero y accesos propios a cotizaciones/pedidos/catálogo. Mantiene las políticas, niveles y controles de precios existentes; no ejecuta otra vez la migración comercial 18.0.1.1.1. Cotizaciones y productos se usan desde sus pantallas nativas.
