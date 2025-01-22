# -*- coding: utf-8 -*-
{
    "name": "Live WebCam Image | Image Widget",
    "version": "16.0.1.3",
    "author": "Bytelegion",
    "website": "http://www.bytelegions.com",
    'company': 'Bytelegion',

    "depends": ["web"],
    "license": "LGPL-3",
    "category": "web",

    "summary": """Allows to take image with WebCam[TAGS], web camera, web photo, web images, camera image,
     snapshot web, snapshot webcam, snapshot picture, web contact image,
     web product image, online mobile web image and product image.""",

    "assets": {
        "web.assets_backend": [
            "legion_webcam_image/static/src/js/webcam_dialog.js",
            "legion_webcam_image/static/src/js/image_field.js",
            "legion_webcam_image/static/src/xml/web_widget_image_webcam.xml",
        ],
    },

    'installable': True,
    'auto_install': False,
    'application': True,
    'images': ['static/description/banner.gif'],
    

}
