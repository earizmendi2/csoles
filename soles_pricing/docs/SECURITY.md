# Seguridad y separación de funciones

| Grupo | Puede hacer | No concede por sí mismo |
|---|---|---|
| Rol vendedor | Cotizaciones y consultas según acceso nativo de Ventas | Porcentaje de descuento, ver costo, aprobar |
| Rol gerente / gerente especial | Consultar ventas de la compañía según grupos nativos | Facultad comercial ni aprobación automática |
| Consultar costos y márgenes | Leer costos y datos económicos protegidos | Editarlos o publicarlos |
| Administrar precios | Familias, segmentos, catálogo comercial, reglas borrador, facultades, rutas y política | Preparar costos, publicar o aprobar |
| Preparar costos comerciales | Crear/editar costos borrador y enviarlos a revisión | Publicar o aprobar |
| Publicar políticas y costos | Publicar/retirar documentos revisados | Editar borradores ni aprobar una cotización |
| Aprobar extraordinarios | Resolver solicitudes asignadas cuando exista facultad `approve` suficiente | Descontar como vendedor ni autoaprobar sin política |

Los grupos pueden combinarse si la empresa así lo decide. Separar funciones requiere asignar usuarios distintos. El superusuario técnico del servidor tiene las facultades normales de superusuario Odoo; ninguna aplicación puede proteger datos de quien controla directamente la base o el código.

La facultad de descuento se evalúa con el usuario que realmente creó o modificó las condiciones comerciales de la línea, registrado por el servidor. Reasignar el vendedor del pedido no permite tomar prestada la facultad de otro usuario. Ese negociador también se excluye de la autoaprobación cuando la política la prohíbe.

Las ACL y reglas de compañía se aplican a modelos propios. Los vendedores ven solicitudes de cotizaciones propias/sin vendedor; los grupos nativos de todas las ventas amplían lectura dentro de compañías permitidas. El servidor comprueba compañía, usuario, facultad, vigencia, condiciones exactas y ruta al aprobar y confirmar.

Costos, márgenes, JSON de valoración y sus versiones están protegidos por grupo y reglas de registro; una vista escondida no es el control de seguridad. Las versiones/bitácoras de costos tampoco se exponen por búsqueda/lectura a vendedores sin permiso. La fachada interna devuelve una lista permitida de campos. El mínimo del vendedor combina el porcentaje permitido, el costo/piso de margen y los mínimos de fabricante. Los límites de importe acumulado también se muestran como motivos y se verifican en servidor.

Las publicaciones, versiones y bitácoras no se modifican o eliminan mediante RPC. El contexto interno de publicación/valoración/anticipo usa identidad Python, no un booleano que pueda enviarse por API. Crear solicitudes y consumirlas se realiza dentro del servidor; los usuarios no pueden asignar estado/aprobador/precio/snapshot mediante una escritura directa. El único campo editable de una solicitud pendiente por un aprobador es el motivo de decisión, si está asignado.

El control se ejecuta en la transición de estado a venta, también por API. Se impide modificar/agregar/eliminar líneas comerciales confirmadas en modos controlados; se permite el flujo nativo de anticipo desde su asistente. Cantidades entregadas, facturadas y otros campos operativos nativos siguen su flujo normal.

Se auditan las publicaciones completas y sus transiciones, borradores de documentos publicados, facultades/rutas, familias, clasificaciones, precedencias, segmentos/marcas y cambios de política de compañía. Cambios relevantes del catálogo y de asignación de segmento dejan valores anteriores/nuevos. El chatter nativo conserva el seguimiento comercial. La bitácora es inmutable para los usuarios, no un registro externo criptográfico.

La invalidación es conservadora: un cambio de política puede invalidar todas las solicitudes abiertas de su compañía. Cambiar una marca compartida afecta todas las compañías. Editar un borrador de regla/costo no invalida solicitudes hasta publicarlo. Los cambios del usuario/grupos se verifican otra vez en el uso de la aprobación.

No se crean usuarios, contraseñas, destinatarios reales ni aprobadores en la instalación. Las pruebas y el comprobador de concurrencia crean usuarios de ejemplo exclusivamente en bases desechables. El cron de vencimiento es interno; las actividades siguen la configuración nativa de correo de la base.
