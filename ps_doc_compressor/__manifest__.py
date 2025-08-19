{
    # Module Information
    "name": "Document Compressor",
    "version": "18.0",
    "category": "custom",
    "summary": "Compress PDF & Image attachments to save storage and optimize Odoo performance",
    "description": """
            attachment compression,
            optimize odoo performance,
            reduce storage,
            pdf image compression,
            odoo database optimization,
            performance boost,
            ir.attachment,
            storage saver,
            image optimizer,
            odoo file size reduction
            Optimize Odoo performance by compressing image and PDF attachments,
            Smart attachment compression to reduce storage & boost system speed
        """,


    # Author
    "author": "Pysquad Informatics LLP",
    "website": "https://odoo.pysquad.com",
    "license": "LGPL-3",

    # Dependencies
    "depends": ["base",],

    # Data File
    "data": [
        'data/cron_job.xml',
    ],
    'images': [
        'static/description/banner_image.png',
    ],

    # Technical Specif.
    'installable': True,
    'application': False,
    'auto_install': False,

    # Other Info
    'price': 10,
    'currency': 'EUR',
}
