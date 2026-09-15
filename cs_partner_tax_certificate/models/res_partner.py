# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from .fiscal_regime_utils import FISCAL_REGIME_SAT_SELECTION

_RFC_RE = re.compile(r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fiscal_regime = fields.Selection(
        selection=FISCAL_REGIME_SAT_SELECTION,
        string='Régimen Fiscal (SAT)',
        help='Régimen fiscal del contribuyente (catálogo SAT). En Enterprise con '
             'Facturación electrónica México también se sincroniza con el campo '
             'estándar de régimen EDI cuando aplica.',
    )
    sat_url = fields.Char(
        string='URL Constancia SAT',
        help='URL de verificación de la Constancia de Situación Fiscal, '
             'extraída del código QR emitido por el SAT.',
    )
    # True si Facturación electrónica México (l10n_mx_edi) está instalada: el régimen
    # se gestiona en Ventas y compras (Información fiscal); no mostrar duplicados.
    cs_tax_cert_hide_fiscal_regime_beside_vat = fields.Boolean(
        compute='_compute_cs_tax_cert_hide_fiscal_regime_beside_vat',
        store=False,
    )

    @api.depends('vat')
    def _compute_cs_tax_cert_hide_fiscal_regime_beside_vat(self):
        hide = bool(
            self.env['ir.module.module'].sudo().search_count([
                ('name', '=', 'l10n_mx_edi'),
                ('state', '=', 'installed'),
            ])
        )
        for partner in self:
            partner.cs_tax_cert_hide_fiscal_regime_beside_vat = hide

    def action_open_sat_url(self):
        self.ensure_one()
        if not self.sat_url:
            raise ValidationError(_('Este contacto no tiene una URL de constancia registrada.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.sat_url,
            'target': 'new',
        }

    @api.constrains('vat', 'country_id')
    def _check_mx_rfc_format(self):
        """RFC mexicano en el NIF estándar (vat) cuando el país es México."""
        for partner in self:
            if not partner.vat or not partner.country_id or partner.country_id.code != 'MX':
                continue
            vat = partner.vat.strip().upper()
            if len(vat) not in (12, 13):
                continue
            if not vat[:1].isalpha():
                continue
            if not _RFC_RE.match(vat):
                raise ValidationError(
                    _('El RFC "%s" en el campo NIF no tiene un formato válido.\n'
                      'Personas morales: 3 letras + 6 dígitos + 3 alfanuméricos.\n'
                      'Personas físicas: 4 letras + 6 dígitos + 3 alfanuméricos.')
                    % vat
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._cs_normalize_vat_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        self._cs_normalize_vat_vals(vals)
        return super().write(vals)

    @api.model
    def _cs_normalize_vat_vals(self, vals):
        vat = vals.get('vat')
        if not vat or not isinstance(vat, str):
            return
        candidate = vat.strip().upper()
        if _RFC_RE.match(candidate):
            vals['vat'] = candidate

    def action_update_from_sat(self):
        self.ensure_one()
        if not self.sat_url:
            raise ValidationError(
                _('Este contacto no tiene URL de Constancia del SAT registrada.')
            )
        wizard = self.env['cs.partner.tax.certificate.update.wizard'].create({
            'partner_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actualizar desde SAT'),
            'res_model': 'cs.partner.tax.certificate.update.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'cs_partner_tax_certificate.view_update_from_sat_wizard_form'
            ).id,
            'target': 'new',
            'context': {'dialog_size': 'xl'},
        }

    def action_open_import_cif_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar desde Constancia Fiscal'),
            'res_model': 'cs.partner.tax.certificate.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_type': 'customer',
            },
        }
