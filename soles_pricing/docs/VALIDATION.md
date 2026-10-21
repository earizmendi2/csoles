# Validación ejecutada · 21 de octubre de 2026

## Resultado

**Instalado y probado realmente en una instancia temporal de Odoo 18.0 Community.** Instalación limpia desde el addon empaquetado/extraído: **33 pruebas transaccionales, 0 fallos y 0 errores**. Segunda ejecución final con actualización del módulo: **33 pruebas, 0 fallos y 0 errores**. Conversor offline: **5 pruebas, todas correctas**. Revisión sintáctica Python/XML, archivos del manifiesto y métodos duplicados: correcta.

El conteo `odoo.tests.stats` muestra 35 porque incluye fases auxiliares; el resumen del ejecutor cuenta 33 casos de negocio. No se presenta como 35 escenarios distintos.

Entorno: macOS local, Python 3.12.14 en entorno virtual temporal, PostgreSQL 18.4 en cluster/socket temporal, código oficial de la rama Odoo `18.0`, dependencias de su `requirements.txt`. Sin Docker, sin base productiva y sin conectar una instancia real de Soles. Los puertos, archivos temporales y bases de validación fueron independientes de cualquier instalación existente.

Archivo oficial descargado: `https://codeload.github.com/odoo/odoo/tar.gz/refs/heads/18.0`. SHA-256 del archivo usado:

```
179923f1167f9e5beca2ff54b85b32fd3aa665834c6f8a5c3adf0c2f5f89445a
```

La rama remota puede avanzar; el hash identifica la instantánea efectivamente probada, no se atribuye a un commit no verificado.

## Escenarios cubiertos

1. Caso histórico Gold 1350, beneficio 2%, facultad 3%, solicitado 1250, costo 1150, margen 8%; bloqueo → solicitud → aprobación → consumo.
2. Confirmación dentro de facultad sin autorización.
3. Separación entre descuento y aprobación, incluso para gerente/aprobador.
4. Prohibición predeterminada de autoaprobación.
5. Cambio/restauración del precio invalida permanentemente esa autorización.
6. Cambios de cotización/términos de pago invalidan solicitudes activas.
7. Cambio/restauración de costo y modificación de reglas invalidan.
8. Consumo de un solo uso, cancelación/regreso a borrador y duplicación.
9. Rechazo de autorizaciones falsificadas, escrituras directas de estado y banderas de contexto.
10. Dos líneas con aprobaciones independientes consumidas en la misma confirmación.
11. Prioridad, cliente/segmento, SKU, volumen y vigencia inclusiva.
12. Facultad personal con prioridad frente a roles.
13. Piso de margen y facultad expresa para exceptuarlo.
14. Caducidad y revocación de facultad.
15. Protección de configuración y campos de costo.
16. Aislamiento de autorizaciones entre vendedores.
17. Aislamiento entre compañías.
18. Descuento sumado/sucesivo, margen y recargo sobre costo.
19. Lista nativa y conversión de UdM a docena.
20. Impuestos incluidos con precio fijo.
21. Simulador y motor coincidentes.
22. Costos superpuestos/faltantes y entradas inválidas.
23. Modo comparación/nativo y protección de condiciones confirmadas.
24. Borrado de línea conservando historial.
25. Captura del porcentaje adicional y control del descuento nativo.
26. Conversión de moneda.
27. Configuración mediante asistente y permisos independientes.
28. Marca, segmento archivado y vista previa de productos.
29. Rechazo con motivo e inmutabilidad de importe autorizado.
30. Lista nativa con impuesto incluido y posición fiscal de exención.
31. Creación de anticipo y factura con el asistente nativo; rechazo de marcas/contextos falsificados.
32. Restricción de fechas históricas y creación de listas no autorizadas.
33. Comparación registra cantidades no admitidas por control activo sin bloquear su confirmación nativa.

El conversor se prueba con mapeos/tasas explícitas, SKU desconocidos, porcentajes inválidos/NaN/infinito, IDs estables y clientes duplicados.

## Revisión en navegador

En una base temporal con datos de muestra se abrieron el módulo, el simulador, la cotización y el detalle de autorización. Se capturó el precio 1250 y se pulsó Simular: el formulario mostró preferente 1323, mínimo 1282.50, costo 1150, margen 8 y motivo de exceso de facultad. Se intentó confirmar sin autorización y se verificó el bloqueo. La autorización estaba vinculada a esa cotización y línea; el administrador de precios no mostraba permiso de aprobar sin el grupo independiente.

Las capturas están en `evidence/` del paquete de fuentes. Se verificó una sesión de navegador de escritorio; no se hizo un tour automatizado completo de todos los grupos/dispositivos. La aprobación y consumo se probaron mediante ORM real en las pruebas transaccionales.

## Evidencia y reproducción

El paquete de fuentes contiene `evidence/odoo_clean_install.log`, `evidence/odoo_final_tests.log`, `evidence/converter_tests.log`, capturas, `validation.json` y sumas SHA-256. Las rutas de código Python/XML/CSV se contrastaron entre fuentes y carpeta extraída que usó Odoo. Las dependencias/servidor de Odoo no se incluyen en el ZIP instalable.

Para reproducir con su instalación, añadir la carpeta del addon al `addons_path`, usar una base vacía o copia de prueba y ejecutar:

```sh
odoo-bin -c /ruta/odoo.conf -d BASE_NUEVA -i soles_pricing \
  --without-demo=all --test-enable --test-tags=/soles_pricing --stop-after-init
python3 -m unittest discover -s soles_pricing/tools -p 'test_*.py' -v
```

Ejecutar sin correos/pagos externos activos. La batería construye su propia configuración en transacciones que se revierten y aísla las reglas/facultades de prueba. No ejecutar pruebas sobre producción.

## Alcance de la afirmación

Esta evidencia confirma instalación, vistas, cálculos y escenarios indicados en **este entorno Odoo 18 Community**. No confirma que funcione sin ajustes en la base productiva de Soles, Enterprise, Studio o módulos no instalados en la prueba. No se ejecutaron PDF por falta de `wkhtmltopdf`, firma/cobro de portal, pruebas de carga ni un ensayo de múltiples procesos concurrentes. Ver [SECURITY.md](SECURITY.md) para compatibilidades y límites pendientes.
