# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
  "name"                 :  "Odoo Google Cloud Storage",
  "summary"              :  """Store your Odoo attachment to Google Cloud Storage""",
  "category"             :  "Document Managment",
  "version"              :  "1.0.3",
  "author"               :  "Webkul Software Pvt. Ltd.",
  "license"              :  "Other proprietary",
  "maintainer"           :  "Kunal Chaudhary Rajora",
  "website"              :  "https://store.webkul.com/Odoo-Google-Cloud-Storage.html",
  "description"          :  """Store your Odoo attachment to Google Cloud Storage""",
  "depends"              :  ['base','web'],
  "data"                 :  ['views/res_config.xml'],
  "images"               :  ['static/description/Banner.png'],
  "application"          :  True,
  "installable"          :  True,
  "auto_install"         :  False,
  "price"                :  169,
  "currency"             :  "USD",
  "pre_init_hook"        :  "pre_init_check",  
  "external_dependencies":  {'python': ['google-cloud-storage']},
}
