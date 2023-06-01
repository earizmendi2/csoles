# -*- coding : utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
	'name'			: 'Invoice Details on Purchase Order',
	'version'		: '15.0.0.1',
	'category'		: 'Purchase',
	'license'		: 'OPL-1',
	'summary'		: 'You can see Invoiced Amount, Invoice Amount Due, Invoice Paid Amount in purchase order',
	'description'	: """You can see invoiced amount, Invoice Amount Due, Invoice Paid Amount in purchase order  
	Invoiced Amount Details For Purchase Order
	Invoice Amount Details For Purchase
	purchase invoice details
	purchase order invoice details
	purchase invoiced details
	purchases invoice details
	invoice amount on purchase order
	invoice amount details on purchase order
	invoice details for purchase order
	invoice detail for purchase order
	invoice detail on purchases
	invoice detail in purchase order
	invoice amount details on purchase order
	""",
	'author'		: 'Browseinfo',
	'website'		: 'https://www.browseinfo.in',
	'depends'		: ['base','purchase','stock'],
	'data'			: [
				   'views/purchase_inherit_views.xml',
				  ],
	'installable'	: True,
	'auto_install'	: False,
	"live_test_url":'https://youtu.be/SC18MCcYCCg',
	"images":['static/description/Banner.png'],
}
