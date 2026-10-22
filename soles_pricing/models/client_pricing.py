from odoo import fields, models, _


class Partner(models.Model):
    _inherit = 'res.partner'

    soles_client_rule_ids = fields.One2many('soles.pricing.rule', 'partner_id', string='Reglas particulares Soles')

    def action_soles_client_rules(self):
        self.ensure_one()
        self.check_access('read')
        partner = self.commercial_partner_id
        action = self.env['ir.actions.actions']._for_xml_id('soles_pricing.action_rule')
        action.update(name=_('Condiciones de %s', partner.display_name),
                      display_name=_('Condiciones de %s', partner.display_name),
                      domain=[('company_id', '=', self.env.company.id), ('partner_id', '=', partner.id)],
                      context={'default_scope': 'partner', 'default_partner_id': partner.id,
                               'default_company_id': self.env.company.id})
        return action

    def action_soles_segment_rules(self):
        self.ensure_one()
        self.check_access('read')
        segment = self.commercial_partner_id.soles_segment_id
        action = self.env['ir.actions.actions']._for_xml_id('soles_pricing.action_rule')
        action.update(name=_('Condiciones del nivel'), display_name=_('Condiciones del nivel'),
                      domain=[('company_id', '=', self.env.company.id), ('scope', '=', 'segment'), ('segment_id', '=', segment.id or 0)],
                      context={'default_scope': 'segment', 'default_segment_id': segment.id,
                               'default_company_id': self.env.company.id})
        return action



class Segment(models.Model):
    _inherit = 'soles.pricing.segment'

    rule_ids = fields.One2many('soles.pricing.rule', 'segment_id', string='Reglas del segmento')
