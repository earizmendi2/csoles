# Soles Pricing · Odoo 18

Módulo instalable para administrar precios comerciales y autorizaciones extraordinarias desde Odoo. Depende de `sale_management`. Licencia LGPL-3. Versión 18.0.1.0.0.

Incluye segmentos editables Gold/Platino/Vibranium, marcas, reglas generales/segmento/cliente, SKU, familias con subfamilias, volumen y vigencias; precios nativos, lista de producto, fijos, costo con margen sobre venta o recargo sobre costo; beneficios de cliente; facultades independientes de descuento/aprobación por grupo o usuario; costos comerciales y pisos de margen; simulador y autorizaciones por línea vinculadas a la cotización, de un solo uso.

Los porcentajes comerciales se capturan en registros de Odoo. No se cargan las tasas 5/7/9 del prototipo ni facultades 3/10 de los ejemplos. Los tres nombres de segmento iniciales pertenecen a la compañía principal y pueden editarse o archivarse. Para otras compañías se crean segmentos propios.

**Inicio seguro:** la instalación deja cada compañía en modo A/Nativo (`off`). Un administrador debe configurar y revisar reglas, costos, roles y facultades antes de activar control. No modifica precios históricos ni importa el catálogo del HTML.

Documentación:

- [Instalación y operación](docs/INSTALL.md)
- [Motor, fórmulas e integración](docs/ARCHITECTURE.md)
- [Seguridad y límites](docs/SECURITY.md)
- [Migración A/B/C/D](docs/MIGRATION.md)
- [Origen y trazabilidad](docs/TRACEABILITY.md)
- [Validación ejecutada](docs/VALIDATION.md)

El ZIP de instalación contiene una sola carpeta `soles_pricing/`. Se extrae en un directorio del `addons_path` de Odoo y se instala desde Aplicaciones o con la CLI. El ZIP de fuentes incluye el mismo código, pruebas, documentación, herramientas de migración y referencias de origen.
