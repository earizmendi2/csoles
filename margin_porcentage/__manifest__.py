# -*- coding: utf-8 -*-
################################################################################
#
#    Ivan Legarda D
#
#    Copyright (C) 2025-TODAY Ivan Legarda D
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
{
    'name': "Invoice margin percentage",
    'version': "16.0.1",
    'category': 'Accounting, Sales',
    'summary': """Show margin summatory in percentage""",
    'description': "It allows to view and analyse the margin in the pivot view on percentage"
                   "",
    'author': "Ivan Legarda D",
    'company': "Ivan Legarda D",
    'maintainer': "Ivan Legarda D",
    'website': "",
    'depends': ['sale_margin', 'account'],
    'data': [
        'views/account_move_views.xml',
        'report/account_invoice_report_views.xml',
        'report/sale_report_views.xml'
    ],
    'images': ['static/description/banner.png'],
    'license': "AGPL-3",
    'installable': True,
    'auto_install': False,
    'application': False
}
