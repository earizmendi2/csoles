# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.cs_partner_tax_certificate.models.fiscal_regime_utils import (
    get_mx_fiscal_regime_selection,
    partner_has_fiscal_regime_selection_field,
)
from odoo.addons.cs_partner_tax_certificate.models.partner_address_utils import (
    partner_address_vals_from_sat,
)


class CsPartnerTaxCertificateImportWizard(models.TransientModel):
    _name = 'cs.partner.tax.certificate.import.wizard'
    _description = 'Importar contacto desde Constancia de Situación Fiscal'

    # ── Paso 1: subir PDF ────────────────────────────────────────

    step = fields.Selection(
        selection=[
            ('upload', 'Subir PDF'),
            ('review', 'Revisar datos'),
            ('confirm_duplicate', 'NIF duplicado'),
        ],
        default='upload',
        required=True,
    )

    duplicate_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto existente con el mismo NIF (RFC)',
        readonly=True,
    )

    pdf_file = fields.Binary(string='Constancia Fiscal (PDF)')
    pdf_filename = fields.Char(string='Nombre del archivo')

    # ── Paso 2: datos extraídos (editables) ──────────────────────

    vat = fields.Char(
        string='RFC (NIF)',
        size=13,
        help='Se guardará en el campo estándar NIF / VAT del contacto.',
    )
    partner_name = fields.Char(string='Razón Social / Nombre')
    street_name = fields.Char(string='Calle (nombre de vialidad)')
    street_number = fields.Char(string='Número exterior')
    street_number2 = fields.Char(string='Número interior')
    colony = fields.Char(string='Colonia')
    locality = fields.Char(string='Localidad')
    city = fields.Char(string='Municipio / Delegación')
    state_id = fields.Many2one(
        comodel_name='res.country.state',
        string='Estado',
        domain=[('country_id.code', '=', 'MX')],
    )
    zip = fields.Char(string='Código Postal', size=5)
    country_id = fields.Many2one(
        comodel_name='res.country',
        string='País',
        default=lambda self: self.env.ref('base.mx', raise_if_not_found=False),
    )
    fiscal_regime = fields.Selection(
        selection='_get_fiscal_regime_selection',
        string='Régimen Fiscal',
    )
    fiscal_regime_text = fields.Char(
        string='Régimen detectado (texto)',
        readonly=True,
    )
    partner_type = fields.Selection(
        selection=[
            ('customer', 'Cliente'),
            ('supplier', 'Proveedor'),
            ('both', 'Cliente y proveedor'),
        ],
        string='Tipo de contacto',
        default='customer',
        required=True,
    )

    sat_url = fields.Char(string='URL de verificación SAT', readonly=True)
    parse_warnings = fields.Text(string='Avisos del parser', readonly=True)
    raw_text = fields.Text(string='Texto extraído del PDF (diagnóstico)', readonly=True)
    mx_edi_regime_available = fields.Boolean(
        string='Hay campo régimen EDI en contactos',
        default=False,
        readonly=True,
    )

    # ── Helpers ──────────────────────────────────────────────────

    @api.model
    def _get_fiscal_regime_selection(self):
        return get_mx_fiscal_regime_selection(self.env)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Crear desde Constancia Fiscal'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'cs_partner_tax_certificate.view_import_from_cif_wizard_form'
            ).id,
            'target': 'new',
            'context': {'dialog_size': 'xl'},
        }

    # ── Acciones ─────────────────────────────────────────────────

    def action_extract(self):
        self.ensure_one()
        if not self.pdf_file:
            raise UserError(_('Suba el archivo PDF de la Constancia Fiscal.'))

        parser = self.env['cs.partner.tax.certificate.parser']
        result = parser.parse(self.pdf_file, self.pdf_filename or 'constancia.pdf')

        if result.get('error'):
            raise UserError(result['error'])

        vals = {
            'step': 'review',
            'vat': result.get('rfc', ''),
            'partner_name': result.get('name', ''),
            'street_name': result.get('street_name', ''),
            'street_number': result.get('street_number', ''),
            'street_number2': result.get('street_number2', ''),
            'colony': result.get('colony', '') or result.get('street2', ''),
            'locality': result.get('locality', ''),
            'city': result.get('city', ''),
            'zip': result.get('zip', ''),
            'fiscal_regime_text': result.get('fiscal_regime_text', ''),
            'fiscal_regime': result.get('fiscal_regime_code') or False,
            'sat_url': result.get('sat_url', ''),
            'parse_warnings': result.get('warnings', ''),
            'raw_text': result.get('raw_text', ''),
            'mx_edi_regime_available': partner_has_fiscal_regime_selection_field(self.env),
        }

        # Resolver estado federativo
        state_name = result.get('state', '').strip()
        if state_name:
            state = self.env['res.country.state'].search(
                [
                    ('name', 'ilike', state_name),
                    ('country_id.code', '=', 'MX'),
                ],
                limit=1,
            )
            if state:
                vals['state_id'] = state.id

        # País México por defecto
        mx = self.env.ref('base.mx', raise_if_not_found=False)
        if mx:
            vals['country_id'] = mx.id

        self.write(vals)
        return self._reopen()

    def action_back(self):
        self.write({'step': 'upload', 'duplicate_partner_id': False})
        return self._reopen()

    def _find_duplicate_by_vat(self, vat_value):
        return self.env['res.partner'].search(
            [
                ('vat', '=', vat_value),
                '|',
                ('company_id', '=', self.env.company.id),
                ('company_id', '=', False),
            ],
            limit=1,
        )

    def _apply_partner_type_ranks(self, vals):
        """
        customer_rank / supplier_rank existen en res.partner solo con account
        instalado (Odoo 18). Con solo contacts el contacto se crea igual.
        """
        partner_fields = self.env['res.partner']._fields
        if self.partner_type in ('customer', 'both') and 'customer_rank' in partner_fields:
            vals['customer_rank'] = 1
        if self.partner_type in ('supplier', 'both') and 'supplier_rank' in partner_fields:
            vals['supplier_rank'] = 1

    def _prepare_partner_vals(self):
        vat_value = self.vat.upper().strip()
        vals = {
            'name': self.partner_name.strip(),
            'vat': vat_value,
            'company_type': 'company' if len(vat_value) == 12 else 'person',
        }

        self._apply_partner_type_ranks(vals)

        address_data = {
            '_nombre_vialidad': self.street_name,
            '_num_ext': self.street_number,
            '_num_int': self.street_number2,
            '_colonia': self.colony,
            '_localidad': self.locality,
            '_municipio': self.city,
            '_estado': self.state_id.name if self.state_id else '',
            'zip': self.zip,
        }
        vals.update(partner_address_vals_from_sat(self.env, address_data))
        if self.state_id:
            vals['state_id'] = self.state_id.id
        if self.country_id:
            vals['country_id'] = self.country_id.id

        partner_fields = self.env['res.partner']._fields
        if self.fiscal_regime:
            if 'l10n_mx_edi_fiscal_regime' in partner_fields:
                vals['l10n_mx_edi_fiscal_regime'] = self.fiscal_regime
            frf = partner_fields.get('fiscal_regime')
            if frf and frf.type == 'selection':
                vals['fiscal_regime'] = self.fiscal_regime

        if self.sat_url:
            vals['sat_url'] = self.sat_url

        return vals

    def _open_partner_form(self, partner):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Contacto'),
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_partner(self):
        self.ensure_one()

        if not self.partner_name:
            raise UserError(_('La razón social / nombre es obligatorio.'))
        if not self.vat:
            raise UserError(_('El RFC (NIF) es obligatorio.'))

        vat_value = self.vat.upper().strip()
        duplicate = self._find_duplicate_by_vat(vat_value)
        if duplicate:
            self.write(
                {
                    'step': 'confirm_duplicate',
                    'duplicate_partner_id': duplicate.id,
                }
            )
            return self._reopen()

        partner = self.env['res.partner'].create(self._prepare_partner_vals())
        return self._open_partner_form(partner)

    def action_confirm_update_existing(self):
        self.ensure_one()
        if not self.duplicate_partner_id:
            raise UserError(_('No hay un contacto seleccionado para actualizar.'))
        self.duplicate_partner_id.write(self._prepare_partner_vals())
        partner = self.duplicate_partner_id
        return self._open_partner_form(partner)

    def action_cancel_duplicate(self):
        self.ensure_one()
        self.write({'step': 'review', 'duplicate_partner_id': False})
        return self._reopen()
