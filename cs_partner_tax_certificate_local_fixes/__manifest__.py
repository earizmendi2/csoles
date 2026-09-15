{
    'name': 'Constancia SAT - Ajustes locales (colonia + extracción de texto)',
    'version': '18.0.1.0.0',
    'summary': (
        'Ajustes locales sobre cs_partner_tax_certificate: agrega el campo '
        'Colonia a Contactos y mejora la extracción de texto del PDF '
        '(nombres y domicilios que llegan pegados sin espacios).'
    ),
    'description': """
Ajustes locales para cs_partner_tax_certificate (Cusoft)
==========================================================

Este módulo NO modifica los archivos originales de cs_partner_tax_certificate
(así conservamos la posibilidad de actualizarlo sin perder nuestros cambios);
en su lugar, hereda/extiende sus modelos.

1) Campo "Colonia" dedicado
---------------------------
cs_partner_tax_certificate ya soporta escribir la colonia en un campo
dedicado `colony` si existe en res.partner (si no, usa `street2` como
respaldo). Este módulo agrega ese campo, así la colonia deja de mezclarse
con "Calle 2".

2) Extracción de texto con PyMuPDF (fitz) en vez de PyPDF2
-----------------------------------------------------------
El PDF de la Constancia de Situación Fiscal usa una fuente que PyPDF2 no
siempre decodifica bien: a veces junta palabras sin espacio ("JUANPEREZ")
y otras las separa letra por letra ("J U A N"). El módulo original ya trae
heurísticas para corregir ambos casos, pero solo pueden reconstruir
espacios en nombres de calles/colonias (usando partículas como "DE",
"SAN", "SANTA"), no en nombres de personas sin esas partículas.

Este parche cambia el motor de extracción de texto a PyMuPDF (que ya es
una dependencia del módulo original, usada para leer el código QR), que
reconstruye espacios de forma mucho más confiable a partir de la posición
real de cada carácter en el PDF. Si PyMuPDF no está disponible o falla,
se usa automáticamente el método original (PyPDF2) como respaldo.

IMPORTANTE: pruébese contra PDFs reales (Persona Física y Persona Moral)
antes de usarse en producción. Un cambio de motor de extracción puede, en
teoría, afectar el orden/formato del texto que leen las demás expresiones
regulares del parser original, así que hay que confirmar que el resto de
los campos (RFC, domicilio, régimen fiscal) se sigan detectando bien.
""",
    'category': 'Sales/CRM',
    'author': 'Rubén Castillo',
    'license': 'LGPL-3',
    'depends': ['cs_partner_tax_certificate'],
    'data': [
        'views/res_partner_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}
