import json

from odoo import http
from odoo.http import request


class DashboardBoard(http.Controller):
    @http.route('/custom_dashboard/dashboard_configuration', type='json', auth="public", website=True)
    def dashboard_configuration(self, data_list, **kwargs):
        """
        When Save Dashboard Button click then update a all Chart Items Positions
        """
        res = json.loads(data_list)
        for dashboard_item_id in res:
            item_id = request.env['eg.custom.dashboard.item'].search([('id', '=', dashboard_item_id.get('item_id'))])
            json_string = json.dumps(dashboard_item_id)
            item_id.write({
                'chart_dashboard_positions': json_string,
            })

    @http.route('/custom_dashboard/dashboard_template_name', type='json', auth="public", website=True)
    def update_dashboard_template_name(self, dashboard_id, template_name):
        dashboard_id = request.env['custom.dashboard.board'].search([('id', '=', dashboard_id)])
        dashboard_id.write({
            'name': template_name,
        })
        return dashboard_id.name,

    @http.route('/custom_dashboard/search_input_chart', type='json', auth="public", website=True)
    def dashboard_search_input_chart(self, search_input, dashboard_item_id):
        dashboard_id = request.env['custom.dashboard.board'].search([('id', '=', dashboard_item_id)])
        chart_item_ids = request.env['eg.custom.dashboard.item'].search(
            [('custom_dashboard_board_id', '=', dashboard_item_id), ('name', 'ilike', search_input)])
        return_dict = {
            'name': dashboard_id.name,
            'dashboard_item_ids': chart_item_ids.ids,
        }
        return return_dict

    @http.route('/custom_dashboard/remove_search_chart', type='json', auth="public", website=True)
    def dashboard_search_show_all_chart(self, dashboard_item_id):
        dashboard_id = request.env['custom.dashboard.board'].search([('id', '=', dashboard_item_id)])

        return_dict = {
            'name': dashboard_id.name,
            'dashboard_item_ids': dashboard_id.custom_dashboard_items_ids.ids,
        }
        return return_dict

    @http.route('/custom_dashboard/update_chart_item_dashboard', type='json', auth="public", website=True)
    def _update_chart_item_or_create_return(self, dashboard_id):
        action = request.env.ref('eg_ai_smart_dashboard_lite.custom_dashboard_client_action').read()[0]
        params = {
            'model': 'custom.dashboard.board',
            'dashboard_board_id': dashboard_id,
        }
        action['context'] = {
            'active_id': dashboard_id
        }
        return dict(action, target='main', params=params)

    @http.route('/custom_dashboard/get_dashboard_items_data', type='json', auth="public", website=True)
    def get_dashboard_items_data(self, dashboard_item_id):
        custom_dashboard_item_id = request.env['eg.custom.dashboard.item'].search([('id', '=', dashboard_item_id)])
        if custom_dashboard_item_id.chart_type in ['bar', 'column']:
            return_dict = {
                'id': custom_dashboard_item_id.id,
                'name': custom_dashboard_item_id.name,
                'chart_theme': custom_dashboard_item_id.chart_theme,
                'color_palette': custom_dashboard_item_id.color_palette,
                'chart_type': custom_dashboard_item_id.chart_type,
                'chart_data': custom_dashboard_item_id.chart_data,
                'chart_background_color': custom_dashboard_item_id.chart_background_color,
                'chart_fore_color': custom_dashboard_item_id.chart_fore_color,
                'chart_dashboard_positions': custom_dashboard_item_id.chart_dashboard_positions,
                'is_distributed_chart': custom_dashboard_item_id.is_distributed_chart,
            }
            return return_dict
        elif custom_dashboard_item_id.chart_type in ['pie']:
            return_dict = {
                'id': custom_dashboard_item_id.id,
                'name': custom_dashboard_item_id.name,
                'chart_data': custom_dashboard_item_id.chart_data,
                'chart_type': custom_dashboard_item_id.chart_type,
                'chart_theme': custom_dashboard_item_id.chart_theme,
                'color_palette': custom_dashboard_item_id.color_palette,
                'chart_dashboard_positions': custom_dashboard_item_id.chart_dashboard_positions,
                'chart_background_color': custom_dashboard_item_id.chart_background_color,
                'chart_fore_color': custom_dashboard_item_id.chart_fore_color,
            }
            return return_dict
        elif custom_dashboard_item_id.chart_type in ['tiles']:
            return_dict = {
                'id': custom_dashboard_item_id.id,
                'name': custom_dashboard_item_id.name,
                'chart_type': custom_dashboard_item_id.chart_type,
                'chart_dashboard_positions': custom_dashboard_item_id.chart_dashboard_positions,
                'tile_image_selection': custom_dashboard_item_id.tile_image_selection,
                'model_name': custom_dashboard_item_id._name,
                'chart_background_color': custom_dashboard_item_id.chart_background_color,
                'chart_fore_color': custom_dashboard_item_id.chart_fore_color,
                'chart_data': custom_dashboard_item_id.chart_data,
                'tile_image_type': custom_dashboard_item_id.tile_image_type,
                'tile_icon': custom_dashboard_item_id.tile_icon,
            }
            return return_dict
        else:
            return_dict = {
                'id': custom_dashboard_item_id.id,
                'name': custom_dashboard_item_id.name,
                'chart_dashboard_positions': custom_dashboard_item_id.chart_dashboard_positions,
                'chart_type': dict(custom_dashboard_item_id._fields['chart_type'].selection).get(custom_dashboard_item_id.chart_type),
            }
            return return_dict
