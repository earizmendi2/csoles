# -*- encoding: utf-8 -*-
########################################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2021 Roberto Barreiro (<roberto@disgal.es>)
#    All Rights Reserved
#
#    Odoo Proprietary License v1.0
#
#    This software and associated files (the "Software") may only be used (executed,
#    modified, executed after modifications) if you have purchased a valid license
#    from the authors, typically via Odoo Apps, or if you have received a written
#    agreement from the authors of the Software (see the COPYRIGHT file).
#
#    You may develop Odoo modules that use the Software as a library (typically
#    by depending on it, importing it and using its resources), but without copying
#    any source code or material from the Software. You may distribute those
#    modules under the license of your choice, provided that this license is
#    compatible with the terms of the Odoo Proprietary License (For example:
#    LGPL, MIT, or proprietary licenses similar to this one).
#
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    The above copyright notice and this permission notice must be included in all
#    copies or substantial portions of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
#########################################################################################

{
    'name': 'Advanced Product Pricelist',
    'summary': 'Print pricelist with product images, product description and more',
    'version': '13.0.0.1',
    'category': 'Product',
    'website': 'https://bitbucket.org/disgalmilladoiro/',
    'author': 'Roberto Barreiro',
    'depends': ['product','sale','sale_management',],
    'data': ['views/report_advanced_product_pricelist_view.xml','wizards/advanced_product_pricelist_view.xml',
    ],
    'images': ['static/description/banner.png','static/description/icon.png','static/description/report_1.png','static/description/report_2.png','static/description/report_3.png','static/description/wizard.png'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'AGPL-3',
    'price': '19.95',
    'currency': 'EUR',
}
