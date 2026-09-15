# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.cs_partner_tax_certificate.models.fiscal_regime_utils import (
    get_mx_fiscal_regime_selection,
    partner_has_fiscal_regime_selection_field,
)
from odoo.addons.cs_partner_tax_certificate.models.dependency_utils import (
    msg_sat_url_not_found,
)
from odoo.addons.cs_partner_tax_certificate.models.partner_address_utils import (
    address_snapshot_from_partner,
    address_snapshot_from_sat_data,
    partner_address_vals_from_sat,
)


class CsPartnerTaxCertificateUpdateWizard(models.TransientModel):
    _name = 'cs.partner.tax.certificate.update.wizard'
    _description = 'Actualizar datos fiscales desde el portal del SAT'

    step = fields.Selection(
        selection=[
            ('fetch', 'Consultar SAT'),
            ('review', 'Revisar cambios'),
        ],
        default='fetch',
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contacto',
        required=True,
        readonly=True,
    )
    sat_consent_accepted = fields.Boolean(
        string='Acepto consultar el SAT',
        help='Confirma que ha leído el aviso de privacidad y desea continuar.',
    )

    sat_rfc = fields.Char(string='RFC (SAT)', readonly=True)
    sat_name = fields.Char(string='Razón Social / Nombre (SAT)', readonly=True)
    sat_street_name = fields.Char(string='Calle (SAT)', readonly=True)
    sat_street_number = fields.Char(string='Número exterior (SAT)', readonly=True)
    sat_street_number2 = fields.Char(string='Número interior (SAT)', readonly=True)
    sat_colony = fields.Char(string='Colonia (SAT)', readonly=True)
    sat_locality = fields.Char(string='Localidad (SAT)', readonly=True)
    sat_city = fields.Char(string='Municipio / Delegación (SAT)', readonly=True)
    sat_state = fields.Char(string='Entidad federativa (SAT)', readonly=True)
    sat_zip = fields.Char(string='Código Postal (SAT)', readonly=True)
    sat_email = fields.Char(string='Correo electrónico (SAT)', readonly=True)
    sat_fiscal_regime_text = fields.Char(string='Régimen(es) detectado(s)', readonly=True)
    sat_fiscal_regime = fields.Selection(
        selection='_get_fiscal_regime_selection',
        string='Clave Régimen (SAT)',
        readonly=True,
    )
    sat_padron_status = fields.Char(string='Estatus en el Padrón', readonly=True)
    sat_start_date = fields.Char(string='Fecha inicio de operaciones', readonly=True)
    sat_last_update = fields.Char(string='Última actualización SAT', readonly=True)
    sat_warning = fields.Char(string='Aviso del SAT', readonly=True)
    can_apply_mx_fiscal_regime = fields.Boolean(default=False)
    has_sat_address = fields.Boolean(readonly=True)

    current_vat = fields.Char(readonly=True)
    current_name = fields.Char(readonly=True)
    current_street_name = fields.Char(string='Calle actual', readonly=True)
    current_street_number = fields.Char(string='Núm. exterior actual', readonly=True)
    current_street_number2 = fields.Char(string='Núm. interior actual', readonly=True)
    current_colony = fields.Char(string='Colonia actual', readonly=True)
    current_locality = fields.Char(string='Localidad actual', readonly=True)
    current_city = fields.Char(string='Municipio actual', readonly=True)
    current_state = fields.Char(string='Estado actual', readonly=True)
    current_zip = fields.Char(readonly=True)
    current_email = fields.Char(readonly=True)
    current_fiscal_regime = fields.Char(readonly=True)

    apply_name = fields.Boolean(string='Actualizar nombre')
    apply_vat = fields.Boolean(string='Actualizar NIF / RFC')
    apply_address = fields.Boolean(
        string='Actualizar domicilio fiscal',
        help='Calle, número exterior, interior, colonia, municipio, estado, CP y correo '
             'en sus campos separados del contacto.',
    )
    apply_fiscal_regime = fields.Boolean(string='Actualizar Régimen Fiscal')

    @api.model
    def _get_fiscal_regime_selection(self):
        return get_mx_fiscal_regime_selection(self.env)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actualizar desde SAT'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'cs_partner_tax_certificate.view_update_from_sat_wizard_form'
            ).id,
            'target': 'new',
            'context': {'dialog_size': 'xl'},
        }

    def _regime_label(self, code: str) -> str:
        return dict(self._get_fiscal_regime_selection()).get(code, code or '')

    def _partner_fiscal_regime_code(self, partner):
        code = getattr(partner, 'l10n_mx_edi_fiscal_regime', None)
        if code:
            return code
        frf = partner._fields.get('fiscal_regime')
        if frf and frf.type == 'selection':
            return partner.fiscal_regime or False
        return False

    @staticmethod
    def _norm(value):
        return (value or '').strip()

    def _address_differs(self, data, partner):
        sat_addr = address_snapshot_from_sat_data(self.env, data)
        if not any(sat_addr.values()):
            return False
        current = address_snapshot_from_partner(partner)
        return any(
            sat_addr[key] and sat_addr[key] != current[key]
            for key in sat_addr
        )

    def _sat_data_from_wizard_fields(self):
        return {
            '_nombre_vialidad': self.sat_street_name,
            '_num_ext': self.sat_street_number,
            '_num_int': self.sat_street_number2,
            '_colonia': self.sat_colony,
            '_localidad': self.sat_locality,
            '_municipio': self.sat_city,
            '_estado': self.sat_state,
            'zip': self.sat_zip,
            'email': self.sat_email,
        }

    def action_fetch_from_sat(self):
        self.ensure_one()
        if not self.sat_consent_accepted:
            raise UserError(
                _('Debe marcar la casilla de consentimiento antes de consultar el SAT.')
            )
        partner = self.partner_id
        if not partner.sat_url:
            raise UserError(msg_sat_url_not_found())

        try:
            data = self.env['cs.partner.tax.certificate.sat.service'].fetch_fiscal_data(
                partner.sat_url
            )
        except UserError:
            raise
        except Exception as exc:
            raise UserError(
                _('Error inesperado al consultar el SAT: %s') % str(exc)
            ) from exc

        regime_code = data.get('fiscal_regime_code') or False

        def _differs(new_val, current_val):
            return bool(new_val) and self._norm(new_val) != self._norm(current_val)

        current_regime = self._partner_fiscal_regime_code(partner)
        has_regime_field = partner_has_fiscal_regime_selection_field(self.env)
        current_addr = address_snapshot_from_partner(partner)
        sat_addr = address_snapshot_from_sat_data(self.env, data)

        self.write({
            'step': 'review',
            'sat_rfc': data.get('rfc', ''),
            'sat_name': data.get('name', ''),
            'sat_street_name': sat_addr['street_name'],
            'sat_street_number': sat_addr['street_number'],
            'sat_street_number2': sat_addr['street_number2'],
            'sat_colony': sat_addr['colony'],
            'sat_locality': sat_addr['locality'],
            'sat_city': sat_addr['city'],
            'sat_state': sat_addr['state'],
            'sat_zip': sat_addr['zip'],
            'sat_email': sat_addr['email'],
            'sat_fiscal_regime_text': data.get('fiscal_regime_text', ''),
            'sat_fiscal_regime': regime_code,
            'sat_padron_status': data.get('padron_status', ''),
            'sat_start_date': data.get('start_date', ''),
            'sat_last_update': data.get('last_update', ''),
            'sat_warning': data.get('warning', ''),
            'can_apply_mx_fiscal_regime': has_regime_field,
            'has_sat_address': any(sat_addr.values()),
            'current_vat': partner.vat or '',
            'current_name': partner.name or '',
            'current_street_name': current_addr['street_name'],
            'current_street_number': current_addr['street_number'],
            'current_street_number2': current_addr['street_number2'],
            'current_colony': current_addr['colony'],
            'current_locality': current_addr['locality'],
            'current_city': current_addr['city'],
            'current_state': current_addr['state'],
            'current_zip': current_addr['zip'],
            'current_email': current_addr['email'],
            'current_fiscal_regime': self._regime_label(current_regime) if current_regime else '',
            'apply_name': _differs(data.get('name'), partner.name),
            'apply_vat': _differs(data.get('rfc'), partner.vat),
            'apply_address': self._address_differs(data, partner),
            'apply_fiscal_regime': bool(
                has_regime_field and regime_code and regime_code != current_regime
            ),
        })
        return self._reopen()

    def action_apply_changes(self):
        self.ensure_one()
        update_vals = {}

        if self.apply_name and self.sat_name:
            update_vals['name'] = self.sat_name.strip()
        if self.apply_vat and self.sat_rfc:
            update_vals['vat'] = self.sat_rfc.upper().strip()
        if self.apply_fiscal_regime and self.sat_fiscal_regime:
            partner_fields = self.env['res.partner']._fields
            if 'l10n_mx_edi_fiscal_regime' in partner_fields:
                update_vals['l10n_mx_edi_fiscal_regime'] = self.sat_fiscal_regime
            frf = partner_fields.get('fiscal_regime')
            if frf and frf.type == 'selection':
                update_vals['fiscal_regime'] = self.sat_fiscal_regime

        if self.apply_address:
            update_vals.update(
                partner_address_vals_from_sat(self.env, self._sat_data_from_wizard_fields())
            )

        if not update_vals:
            raise UserError(_('Seleccione al menos un campo para actualizar.'))

        self.partner_id.write(update_vals)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
