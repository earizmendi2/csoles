# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2023-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
{
    "name": "Sales Target VS Achievement Reduce Price",
    "version": "16.0.1.0.0",
    'category': 'Sales, CRM',
    "summary": "Sales Target and Achievements based on Salesperson's taking price reduce before tax "
               "individual target",
    "description": """Based on Salesperson's individual target, Sales Target 
     and Achievement calculation for Salesperson and CRM Sales Team using price reduced""",
    'author': 'Ivan Legarda ed',
    'company': 'Ivan Legarda ed',
    'maintainer': 'Ivan Legarda',
    'website': "https://www.odoo.com",
    'depends': ['base', 'sale_management', 'crm', 'mail'],
    'data': ['security/sales_target_vs_achievement_groups.xml',
             'security/ir.model.access.csv',
             'views/target_achieve_views.xml',
             'views/crm_team_views.xml'],
    'images': ['static/description/banner.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
