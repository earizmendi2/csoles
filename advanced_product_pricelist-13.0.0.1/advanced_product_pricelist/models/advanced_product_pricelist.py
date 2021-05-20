# -*- encoding: utf-8 -*-
# Copyright 2021 Roberto Barreiro
# Copyright 2017 Tecnativa - Carlos Dauden
# Copyright 2018 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class AdvancedProductPricelist(models.TransientModel):

    _name = 'advanced.product.pricelist'

    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist',
        required=True
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
    )
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Customers',
    )
    categ_ids = fields.Many2many(
        comodel_name='product.category',
        string='Categories',
    )
    show_variants = fields.Boolean(string='Show Variants', default=True)
    product_tmpl_ids = fields.Many2many(
        comodel_name='product.template',
        string='Products',
        help='Keep empty for all products',
    )
    product_ids = fields.Many2many(
        comodel_name='product.product',
        string='Products',
        help='Keep empty for all products',
    )
    show_standard_price = fields.Boolean(string='Show Cost Price')
    show_sale_price = fields.Boolean(string='Show Sale Price')
    order_field = fields.Selection([
        ('name', 'Name'),
        ('default_code', 'Internal Reference'),
    ], string='Order', default='name')
    show_image = fields.Boolean(string='Show Product Image', default=True)
    image_size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('big', 'Big'),
        ], string='Image Size', default='small')
    show_description = fields.Boolean(string='Show Product Description')

    @api.model
    def default_get(self, fields):
        res = super(AdvancedProductPricelist, self).default_get(fields)
        if self.env.context.get('active_model') == 'product.template':
            res['product_tmpl_ids'] = [
                (6, 0, self.env.context.get('active_ids', []))]
        elif self.env.context.get('active_model') == 'product.product':
            res['show_variants'] = True
            res['product_ids'] = [
                (6, 0, self.env.context.get('active_ids', []))]
        elif self.env.context.get('active_model') == 'product.pricelist':
            res['pricelist_id'] = self.env.context.get('active_id', False)
        elif self.env.context.get('active_model') == 'res.partner':
            active_ids = self.env.context.get('active_ids', [])
            res['partner_ids'] = [(6, 0, active_ids)]
            if len(active_ids) == 1:
                partner = self.env['res.partner'].browse(active_ids[0])
                res['pricelist_id'] = partner.property_product_pricelist.id
        elif self.env.context.get('active_model') == 'product.pricelist.item':
            active_ids = self.env.context.get('active_ids', [])
            items = self.env['product.pricelist.item'].browse(active_ids)
            # Set pricelist if all the items belong to the same one
            if len(items.mapped('pricelist_id')) == 1:
                res['pricelist_id'] = items[0].pricelist_id.id
            product_items = items.filtered(
                lambda x: x.applied_on == '0_product_variant')
            template_items = items.filtered(
                lambda x: x.applied_on == '1_product')
            category_items = items.filtered(
                lambda x: x.applied_on == '2_product_category')
            # Convert al pricelist items to their affected variants
            if product_items:
                res['show_variants'] = True
                product_ids = product_items.mapped('product_id')
                product_ids |= template_items.mapped(
                    'product_tmpl_id.product_variant_ids')
                product_ids |= product_ids.search([
                    ('sale_ok', '=', True),
                    ('categ_id', 'in', category_items.mapped('categ_id').ids)
                ])
                res['product_ids'] = [(6, 0, product_ids.ids)]
            # Convert al pricelist items to their affected templates
            if template_items and not product_items:
                product_tmpl_ids = template_items.mapped('product_tmpl_id')
                product_tmpl_ids |= product_tmpl_ids.search([
                    ('sale_ok', '=', True),
                    ('categ_id', 'in', category_items.mapped('categ_id').ids)
                ])
                res['product_tmpl_ids'] = [
                    (6, 0, product_tmpl_ids.ids)]
            # Only category items, we just set the categories
            if category_items and not product_items and not template_items:
                res['categ_ids'] = [
                    (6, 0, category_items.mapped('categ_id').ids)]
        return res


    def get_pricelist_to_print(self):
        self.ensure_one()
        pricelist = self.pricelist_id
        if not pricelist and self.partner_count == 1:
            pricelist = self.partner_ids[0].property_product_pricelist
        return pricelist

    def print_report(self):
        if not(self.pricelist_id or self.show_standard_price or self.show_sale_price):
            raise ValidationError(_(
                'You must set price list or any customer '
                'or any show price option.'))
        return self.env.ref(
            'advanced_product_pricelist.'
            'action_advanced_product_pricelist').report_action(self)

class ProductProduct(models.Model):
    _inherit = "product.product"

    product_print_pricelist = fields.Boolean(string='Print on Pricelist', default=True)

class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_print_pricelist = fields.Boolean(string='Print on Pricelist', default=True)
