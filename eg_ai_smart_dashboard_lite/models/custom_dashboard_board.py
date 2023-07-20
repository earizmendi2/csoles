from odoo import models, fields, api


class CustomDashboardBoard(models.Model):
    _name = 'custom.dashboard.board'
    _description = 'Custom Dashboard Board'

    name = fields.Char(string='Name')
    custom_dashboard_items_ids = fields.One2many(comodel_name='eg.custom.dashboard.item',
                                                 inverse_name='custom_dashboard_board_id', string='Dashboard Items')
    count_total_items = fields.Float(string='Total Items', compute='_compute_count_total_items')
    color = fields.Char(string='Color')

    @api.depends('custom_dashboard_items_ids')
    def _compute_count_total_items(self):
        for rec in self:
            rec.count_total_items = len(rec.custom_dashboard_items_ids.ids)

    def get_main_dashboard_view(self):
        action = self.env.ref('eg_ai_smart_dashboard_lite.custom_dashboard_client_action').read()[0]
        params = {
            'model': 'custom.dashboard.board',
            'dashboard_board_id': self.id,
            # 'nomenclature_id': [self.env.company.nomenclature_id],
        }
        return dict(action, target='main', params=params)

    @api.model
    def _update_chart_item_or_create_return(self, dashboard_id):
        action = self.env.ref('eg_ai_smart_dashboard_lite.custom_dashboard_client_action').read()[0]
        params = {
            'model': 'custom.dashboard.board',
            'dashboard_board_id': dashboard_id,
        }
        return dict(action, target='main', params=params)

    @api.model
    def get_dashboard_items_lines(self, dashboard_board_id):
        dashboard_item_ids = self.search([('id', '=', dashboard_board_id)])
        group_custom_dashboard_manager = self.user_has_groups('eg_ai_smart_dashboard_lite.custom_dashboard_manager')
        return_dict = {
            'name': dashboard_item_ids.name,
            'dashboard_item_ids': dashboard_item_ids.custom_dashboard_items_ids.ids,
            'group_custom_dashboard_manager': group_custom_dashboard_manager,
        }
        return return_dict
