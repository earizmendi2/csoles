from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class Approval(models.Model):
    _name = 'soles.pricing.approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Autorización extraordinaria de un solo uso'
    _check_company_auto = True
    _order = 'id desc'
    _rec_name = 'order_id'

    order_id = fields.Many2one('sale.order', string='Cotización', required=True, ondelete='restrict', check_company=True, index=True)
    line_id = fields.Many2one('sale.order.line', string='Línea', ondelete='set null', check_company=True, index=True)
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    currency_id = fields.Many2one(related='order_id.currency_id')
    state = fields.Selection([('pending', 'Pendiente'), ('approved', 'Aprobada'), ('rejected', 'Rechazada'), ('invalid', 'Invalidada'), ('consumed', 'Consumida')], default='pending', required=True, tracking=True, copy=False)
    requester_id = fields.Many2one('res.users', string='Solicitante', required=True, ondelete='restrict')
    reason = fields.Text(string='Motivo de solicitud', required=True)
    fingerprint = fields.Char(required=True, copy=False)
    requested_price = fields.Monetary(string='Precio neto autorizado por unidad', required=True)
    requested_extra = fields.Float(string='Descuento adicional solicitado (%)')
    cost_snapshot = fields.Monetary(string='Costo comercial al solicitar', groups='soles_pricing.group_cost')
    margin_snapshot = fields.Float(string='Margen al solicitar (%)', groups='soles_pricing.group_cost')
    approver_id = fields.Many2one('res.users', string='Decidido por', ondelete='restrict', copy=False)
    approved_at = fields.Datetime(string='Aprobada el', copy=False)
    expires_at = fields.Datetime(string='Vence el', copy=False)
    consumed_at = fields.Datetime(string='Consumida el', copy=False)
    decision_reason = fields.Text(string='Motivo de decisión')
    authority_id = fields.Many2one('soles.pricing.authority', ondelete='restrict', copy=False)
    authority_version = fields.Char(copy=False)
    effective_valid = fields.Boolean(compute='_compute_effective', string='Válida actualmente')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Solicite la autorización desde la línea de cotización.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            self.check_access('write')
            if set(vals) - {'decision_reason'} or not self.env.user.has_group('soles_pricing.group_approver') or self.filtered(lambda r: r.state != 'pending'):
                raise AccessError(_('Las autorizaciones son inmutables; use los botones del flujo.'))
        return super().write(vals)

    def unlink(self):
        raise AccessError(_('El historial de autorizaciones no se elimina.'))

    @api.constrains('line_id', 'order_id')
    def _check_line_order(self):
        for rec in self:
            if rec.line_id and rec.line_id.order_id != rec.order_id:
                raise UserError(_('La línea debe pertenecer a la cotización.'))

    def _approver_authority(self, user):
        self.ensure_one()
        rec = self.sudo()
        order = rec.order_id
        ev = rec.line_id._soles_evaluate()
        if not user.active or not user.has_group('soles_pricing.group_approver') or order.company_id not in user.company_ids:
            return self.env['soles.pricing.authority']
        if not order.company_id.soles_allow_self_approval and user in (rec.requester_id | order.user_id):
            return self.env['soles.pricing.authority']
        if (order.company_id.soles_require_cost and ev['cost'] <= 0) or ev['requested'] <= 0:
            return self.env['soles.pricing.authority']
        authority = self.env['soles.pricing.engine']._authority(
            'approve', user, order.company_id, order.partner_id, rec.line_id.product_id,
            ev['qty_base'], order.soles_pricing_date)
        floor = authority.min_margin if authority else 0
        if authority and not authority.override_floor:
            floor = max(floor, ev['floor'])
        if authority and ev['extra'] <= authority.max_discount + 1e-8 and ev['margin'] + 1e-8 >= floor:
            return authority
        return self.env['soles.pricing.authority']

    def _usable(self):
        self.ensure_one()
        rec = self.sudo()
        if not rec.line_id or rec.state != 'approved' or not rec.expires_at or fields.Datetime.now() >= rec.expires_at:
            return False
        if rec.fingerprint != rec.order_id._soles_snapshot():
            return False
        authority = rec._approver_authority(rec.approver_id)
        return bool(authority and authority == rec.authority_id and str(authority.write_date) == rec.authority_version)

    def _compute_effective(self):
        for rec in self:
            rec.effective_valid = rec._usable()

    def _check_reviewer(self):
        self.check_access('read')
        if not self.env.user.has_group('soles_pricing.group_approver'):
            raise AccessError(_('No tiene permiso para aprobar o rechazar.'))
        self.order_id._soles_lock()
        if self.filtered(lambda r: r.state != 'pending' or r.order_id.state not in ('draft', 'sent')):
            raise UserError(_('La solicitud ya no está pendiente en una cotización.'))

    def action_approve(self):
        self._check_reviewer()
        for rec in self:
            if rec.fingerprint != rec.order_id._soles_snapshot():
                raise UserError(_('La cotización cambió. Solicite una nueva autorización.'))
            authority = rec._approver_authority(self.env.user)
            if not authority:
                raise AccessError(_('Su facultad de aprobación no cubre este descuento/margen, falta costo o es autoaprobación.'))
            now = fields.Datetime.now()
            rec.sudo().write({'state': 'approved', 'approver_id': self.env.user.id, 'approved_at': now,
                              'expires_at': now + timedelta(hours=rec.company_id.soles_approval_hours),
                              'authority_id': authority.id, 'authority_version': str(authority.write_date)})
            rec.order_id.message_post(body=_('Aprobación extraordinaria de un solo uso para %s.', rec.line_id.product_id.display_name))
        return True

    def action_reject(self):
        self._check_reviewer()
        if self.filtered(lambda r: not r.decision_reason):
            raise UserError(_('Indique el motivo del rechazo.'))
        self.sudo().write({'state': 'rejected', 'approver_id': self.env.user.id})
        return True

    def action_check_validity(self):
        self.check_access('read')
        self.order_id._soles_lock()
        self.filtered(lambda r: r.state == 'approved' and not r._usable()).sudo().write({'state': 'invalid'})
        return True
