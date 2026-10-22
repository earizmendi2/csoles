from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class Approval(models.Model):
    _name = 'soles.pricing.approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Autorización extraordinaria de un solo uso'
    _check_company_auto = True
    _order = 'id desc'
    _rec_name = 'name'

    name = fields.Char(string='Solicitud', readonly=True, copy=False, default='/')
    order_id = fields.Many2one('sale.order', string='Cotización', required=True, ondelete='restrict', check_company=True, index=True)
    line_id = fields.Many2one('sale.order.line', string='Línea', ondelete='set null', check_company=True, index=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True, index=True)
    currency_id = fields.Many2one('res.currency', required=True, readonly=True)
    company_currency_id = fields.Many2one('res.currency', string='Moneda de compañía', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Cliente aprobado', readonly=True)
    product_id = fields.Many2one('product.product', string='SKU aprobado', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UdM aprobada', readonly=True)
    quantity = fields.Float(string='Cantidad aprobada', readonly=True)
    base_price = fields.Monetary(string='Precio base', readonly=True)
    preferred_price = fields.Monetary(string='Precio preferencial', readonly=True)
    discount_amount = fields.Monetary(string='Descuento total de la oferta', currency_field='company_currency_id', readonly=True)
    order_amount = fields.Monetary(string='Importe neto de la oferta', currency_field='company_currency_id', readonly=True)
    route_id = fields.Many2one('soles.pricing.route', string='Ruta de aprobación', readonly=True, ondelete='restrict')
    reviewer_ids = fields.Many2many('res.users', string='Responsables asignados', readonly=True, copy=False)
    routing_note = fields.Char(string='Resultado de enrutamiento', readonly=True)
    state = fields.Selection([('pending', 'Pendiente'), ('approved', 'Aprobada'), ('rejected', 'Rechazada'), ('cancelled', 'Cancelada'), ('expired', 'Vencida'), ('invalid', 'Invalidada'), ('consumed', 'Consumida')], string='Estado', default='pending', required=True, tracking=True, copy=False)
    requester_id = fields.Many2one('res.users', string='Solicitante', required=True, ondelete='restrict')
    reason = fields.Text(string='Motivo comercial', required=True)
    fingerprint = fields.Char(required=True, copy=False, string='Huella de condiciones')
    requested_price = fields.Monetary(string='Precio neto por unidad', required=True)
    requested_extra = fields.Float(string='Adicional solicitado sobre preferencial (%)')
    cost_snapshot = fields.Monetary(string='Costo evaluado', groups='soles_pricing.group_cost')
    margin_snapshot = fields.Float(string='Margen evaluado (%)', groups='soles_pricing.group_cost')
    approver_id = fields.Many2one('res.users', string='Decidido por', ondelete='restrict', copy=False)
    approved_at = fields.Datetime(string='Aprobada el', copy=False)
    resolved_at = fields.Datetime(string='Resuelta el', copy=False)
    expires_at = fields.Datetime(string='Vence el', copy=False)
    consumed_at = fields.Datetime(string='Consumida el', copy=False)
    consumption_count = fields.Integer(string='Consumos', default=0, readonly=True, copy=False)
    decision_reason = fields.Text(string='Motivo de decisión')
    authority_id = fields.Many2one('soles.pricing.authority', string='Facultad aplicada', ondelete='restrict', copy=False)
    authority_version = fields.Char(copy=False)
    effective_valid = fields.Boolean(compute='_compute_effective', string='Válida actualmente')

    can_decide = fields.Boolean(compute='_compute_user_actions')
    can_cancel = fields.Boolean(compute='_compute_user_actions')

    @api.depends_context('uid')
    @api.depends('state', 'reviewer_ids', 'requester_id')
    def _compute_user_actions(self):
        for rec in self:
            pending = rec.state == 'pending'
            assigned = self.env.user in rec.reviewer_ids
            rec.can_decide = pending and assigned and self.env.user.has_group('soles_pricing.group_approver')
            rec.can_cancel = pending and (assigned or rec.requester_id == self.env.user)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Solicite la autorización desde la línea.'))
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('soles.pricing.approval') or '/'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            self.check_access('write')
            if set(vals) - {'decision_reason'} or not self.env.user.has_group('soles_pricing.group_approver') or self.filtered(lambda r: r.state != 'pending' or self.env.user not in r.reviewer_ids):
                raise AccessError(_('Use el flujo; solo el responsable puede registrar la decisión pendiente.'))
        if vals.get('state') == 'consumed' and self.filtered(lambda r: r.state != 'approved' or r.consumption_count):
            raise UserError(_('La autorización no puede consumirse de nuevo.'))
        if vals.get('state') == 'consumed':
            vals = dict(vals, consumption_count=1)
        result = super().write(vals)
        if vals.get('state') in ('approved', 'rejected', 'invalid', 'cancelled', 'expired', 'consumed'):
            self.sudo().activity_ids.action_feedback(feedback=_('Solicitud resuelta o invalidada.'))
        return result

    def unlink(self):
        raise AccessError(_('El historial no se elimina.'))

    @api.constrains('line_id', 'order_id', 'company_id')
    def _check_line_order(self):
        for rec in self:
            if rec.line_id and rec.line_id.order_id != rec.order_id:
                raise UserError(_('La línea debe pertenecer a la cotización.'))
            if rec.order_id.company_id != rec.company_id:
                raise UserError(_('La solicitud conserva su compañía original.'))

    def _approver_authority(self, user):
        self.ensure_one()
        rec = self.sudo()
        return self.env['soles.pricing.engine']._approval_authority(user=user, company=rec.company_id,
            partner=rec.order_id.partner_id, product=rec.line_id.product_id, currency=rec.currency_id,
            ev=rec.line_id._soles_evaluate(), requester=rec.requester_id | rec.line_id.soles_negotiator_id, seller=rec.order_id.user_id)

    def _select_route(self):
        self.ensure_one()
        rec = self.sudo()
        return self.env['soles.pricing.engine']._approval_route(company=rec.company_id,
            partner=rec.order_id.partner_id, product=rec.line_id.product_id, currency=rec.currency_id,
            ev=rec.line_id._soles_evaluate(), requester=rec.requester_id | rec.line_id.soles_negotiator_id, seller=rec.order_id.user_id)

    def _notify_reviewers(self):
        for rec in self.sudo():
            route, users = rec._select_route()
            rec.write({'route_id': route.id, 'reviewer_ids': [(6, 0, users.ids)],
                       'routing_note': _('Responsables con facultad suficiente') if users else _('Sin responsable elegible: revisar matriz y facultades')})
            if rec.state == 'pending' and rec.company_id.soles_notify_reviewers:
                for user in users:
                    rec.activity_schedule('mail.mail_activity_data_todo', user_id=user.id,
                        summary=_('Revisar precio extraordinario'), note=_('Revise precio, margen, importe y motivo en esta solicitud.'))

    def _usable(self):
        self.ensure_one()
        rec = self.sudo()
        if not rec.line_id or rec.state != 'approved' or not rec.expires_at or fields.Datetime.now() >= rec.expires_at or rec.consumption_count:
            return False
        if rec.fingerprint != rec.order_id._soles_snapshot():
            return False
        route, users = rec._select_route()
        if route != rec.route_id or rec.approver_id not in users:
            return False
        authority = rec._approver_authority(rec.approver_id)
        return bool(authority and authority == rec.authority_id and str(authority.write_date) == rec.authority_version)

    def _compute_effective(self):
        for rec in self:
            rec.effective_valid = rec._usable()

    def _check_reviewer(self):
        self.check_access('read')
        if not self.env.user.has_group('soles_pricing.group_approver'):
            raise AccessError(_('No tiene permiso comercial de aprobación.'))
        self.order_id._soles_lock()
        if self.filtered(lambda r: r.state != 'pending' or r.order_id.state not in ('draft', 'sent')):
            raise UserError(_('La solicitud ya no está pendiente.'))
        for rec in self:
            route, users = rec._select_route()
            if route != rec.route_id or self.env.user not in users or self.env.user not in rec.reviewer_ids:
                raise AccessError(_('No está asignado a la ruta elegible de esta solicitud.'))
            if not rec.decision_reason:
                raise UserError(_('Registre el motivo de su decisión.'))

    def action_approve(self):
        self._check_reviewer()
        for rec in self:
            if rec.fingerprint != rec.order_id._soles_snapshot():
                raise UserError(_('Las condiciones cambiaron; solicite otra autorización.'))
            authority = rec._approver_authority(self.env.user)
            now = fields.Datetime.now()
            rec.sudo().write({'state': 'approved', 'approver_id': self.env.user.id, 'approved_at': now, 'resolved_at': now,
                'expires_at': now + timedelta(hours=rec.company_id.soles_approval_hours),
                'authority_id': authority.id, 'authority_version': str(authority.write_date)})
            rec.order_id.message_post(body=_('Autorización de un solo uso aprobada: %s', rec.name))
        return True

    def action_reject(self):
        self._check_reviewer()
        self.sudo().write({'state': 'rejected', 'approver_id': self.env.user.id, 'resolved_at': fields.Datetime.now()})
        return True

    def action_cancel(self):
        self.check_access('read')
        if self.filtered(lambda r: r.state != 'pending' or (r.requester_id != self.env.user and self.env.user not in r.reviewer_ids)):
            raise AccessError(_('Solo solicitante o responsable puede cancelar una pendiente.'))
        self.order_id._soles_lock()
        self.sudo().write({'state': 'cancelled', 'resolved_at': fields.Datetime.now()})
        return True

    def action_check_validity(self):
        self.check_access('read')
        self.order_id._soles_lock()
        self.filtered(lambda r: r.state == 'approved' and r.expires_at <= fields.Datetime.now()).sudo().write({'state': 'expired'})
        self.filtered(lambda r: r.state == 'approved' and not r._usable()).sudo().write({'state': 'invalid'})
        return True

    @api.model
    def _cron_expire(self):
        self.sudo().search([('state', '=', 'approved'), ('expires_at', '<=', fields.Datetime.now())]).write({'state': 'expired'})
