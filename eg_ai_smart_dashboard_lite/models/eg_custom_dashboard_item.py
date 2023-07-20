import json

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools import date_utils


class EgCustomDashboardItem(models.Model):
    _name = 'eg.custom.dashboard.item'
    _description = 'Eg Custom Dashboard Item'

    name = fields.Char(string='Name')
    chart_type = fields.Selection(
        [('bar', 'Bar Chart'), ('pie', 'Pie Chart'), ('column', 'Column Chart'), ('donut', 'Donut Chart'),
         ('line', 'Line Chart'), ('area', 'Area Chart'), ('treemap', 'Treemap'), ('radar', 'Radar Chart'),
         ('polarArea', 'Polar Area'),
         ('tiles', 'Tiles'), ('list', 'List'), ('kpi', 'KPI')],
        default=lambda self: self._context.get('chart_type'),
        required=True)
    custom_dashboard_board_id = fields.Many2one(comodel_name='custom.dashboard.board',
                                                default=lambda self: self._context.get('custom_dashboard_board_id'))
    # odoo fields, models
    ir_model_id = fields.Many2one(comodel_name='ir.model', string='Model Name')
    model_name = fields.Char(string="Model Name")
    measure_model_field_ids = fields.Many2many(comodel_name='ir.model.fields',
                                               domain="[('model_id','=',ir_model_id),('name','!=','id'),('store','=',True),'|','|',('ttype','=','integer'),('ttype','=','float'),('ttype','=','monetary')]")
    label_model_field_id = fields.Many2one(comodel_name='ir.model.fields',
                                           domain="[('model_id','=',ir_model_id), ('name','!=','id'), ('store','=',True),('ttype','!=','boolean'), ('ttype','!=','binary'), ('ttype','!=','many2many'), ('ttype','!=','one2many')]")
    list_view_field_ids = fields.Many2many(comodel_name='ir.model.fields', relation='list_view_fields_rel',
                                           domain="[('model_id','=',ir_model_id), ('name','!=','id'), ('store','=',True),('ttype','!=','boolean'), ('ttype','!=','binary'), ('ttype','!=','many2many'), ('ttype','!=','one2many')]")
    record_limit = fields.Integer(string='Record Limit')
    record_sort_field = fields.Many2one(comodel_name='ir.model.fields',
                                        domain="[('model_id','=',ir_model_id),('name','!=','id'),('ttype','!=','binary'),('store','=',True),('ttype','!=','one2many')]")
    record_sort = fields.Selection([('ASC', 'Ascending'), ('DESC', 'Descending')], default='ASC', string='Record Sort')
    filter_domain = fields.Char(string="Domain")
    # KPI
    kpi_model_id = fields.Many2one(comodel_name='ir.model', string='Model Name')
    kpi_model_name = fields.Char(string="Model Name")
    kpi_calculation_type = fields.Selection([('count', 'Count'), ('sum', 'Sum')], default='sum',
                                            string='Calculation Type')
    kpi_measure_field_id = fields.Many2one(comodel_name='ir.model.fields',
                                           domain="[('model_id','=',kpi_model_id),('name','!=','id'),('store','=',True),'|','|',('ttype','=','integer'),('ttype','=','float'),('ttype','=','monetary')]",
                                           string='Measure Field')
    kpi_data_calculation_type = fields.Selection(
        [('none', 'None'), ('sum', 'Sum'), ('ratio', 'Ratio'), ('percentage', 'Percentage')],
        string='Data Calculation Type', default='none')
    kpi_filter_domain = fields.Char(string='Domain')
    kpi_date_filter_field_id = fields.Many2one(comodel_name='ir.model.fields', string='Date Filter Field',
                                               domain="[('model_id','=',kpi_model_id), '|',('ttype','=','datetime'),('ttype','=','date')]")
    kpi_date_record_filter_type = fields.Selection(
        [('none', 'None'), ('today', 'Today'), ('this_week', 'This Week'), ('this_month', 'This Month'),
         ('last_month', 'Last Month'),
         ('last_week', 'Last Week'), ('this_year', 'This Year'), ('last_year', 'Last Year'),
         ('last_90_days', 'Last 90 Days'), ('last_15_days', 'Last 15 days'), ('custom_filter', 'Custom Filter')],
        default='none', string='Date Filter Type')
    kpi_start_date = fields.Datetime('Start Date')
    kpi_end_date = fields.Datetime('End Date')
    kpi_record_amount = fields.Float(string='Record Amount')
    # odoo date filter
    date_record_filter_type = fields.Selection(
        [('none', 'None'), ('today', 'Today'), ('this_week', 'This Week'), ('this_month', 'This Month'),
         ('last_month', 'Last Month'),
         ('last_week', 'Last Week'), ('this_year', 'This Year'), ('last_year', 'Last Year'),
         ('last_90_days', 'Last 90 Days'), ('last_15_days', 'Last 15 days'), ('custom_filter', 'Custom Filter')],
        default='none')
    date_filter_field = fields.Many2one(comodel_name='ir.model.fields', string='Date Filter Field',
                                        domain="[('model_id','=',ir_model_id), '|',('ttype','=','datetime'),('ttype','=','date')]")
    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
    # chart configuration
    name_align_position = fields.Selection([('left', 'Left'), ('center', 'Center'), ('right', 'Right')],
                                           default='center')
    chart_theme = fields.Selection([('light', 'Light'), ('dark', 'Dark'), ('custom', 'Custom')], default='light',
                                   string='Chart Theme')
    color_palette = fields.Selection(
        [('palette1', 'Palette-1'), ('palette2', 'Palette-2'), ('palette3', 'Palette-3'), ('palette4', 'Palette-4'),
         ('palette5', 'Palette-5'), ('palette6', 'Palette-6'), ('palette7', 'Palette-7'), ('palette8', 'Palette-8'),
         ('palette9', 'Palette-9'), ('palette10', 'Palette-10')], default='palette1', string='Color Palette')
    # Chart Grid Configurations
    is_show_grid = fields.Boolean(string='Enable Show Grid')
    grid_position = fields.Selection([('front', 'Front'), ('back', 'Back')], string='Grid Position', default='back')
    grid_color = fields.Char(string="Grid Color", default="#90A4AE")
    stork_dash_array = fields.Float(string='Space between dashes', default=0)
    is_enable_x_axis = fields.Boolean(string='Enable show X Axis')
    is_enable_y_axis = fields.Boolean(string='Enable show Y Axis')
    # stork type for Line Chart
    stork_type = fields.Selection([('smooth', 'Smooth'), ('straight', 'Straight'), ('stepline', 'Stepline')],
                                  string='Stork Line Type', default='straight')
    is_show_datalabels = fields.Boolean(string='Enable show Datalabels')
    datalabels_unit = fields.Char(string='Datalabels Unit')
    is_treemap_distributed = fields.Boolean(string='Treemap Distributed')

    tile_image_type = fields.Selection([('default_icons', 'Default Icons'), ('custom_icon', 'Custom Icon or Image')],
                                       default='default_icons')
    tile_image_selection = fields.Binary(string='Custom Icon or Image')
    tile_icon = fields.Char(string='Tile Icon')
    tile_unit = fields.Char(string='Tile Unit')
    tile_record_amount = fields.Float('Record Amount')
    calculation_type = fields.Selection([('count', 'Count'), ('sum', 'Sum')], default='sum')
    graph_preview = fields.Char(string='Graph Preview')
    chart_data = fields.Char(string='Chart data', compute='_compute_chart_chart')
    # Chart Legend
    is_check_show_legend = fields.Boolean(string='Is Check show Legend Field')
    is_show_legend = fields.Boolean(string='Enable show Legend')
    legend_position = fields.Selection([('top', 'Top'), ('right', 'Right'), ('bottom', 'Bottom'), ('left', 'Left')],
                                       string='Legend Position')
    legend_horizontal_align = fields.Selection([('center', 'center'), ('left', 'Left'), ('right', 'Right')],
                                               string='Legend Horizontal Align')

    is_chart_zoom = fields.Boolean(string='Enable Chart Zoom')
    is_stack_chart = fields.Boolean(string='Stack Chart')

    is_distributed_chart = fields.Boolean(string='Distributed Chart')
    is_reserved_chart = fields.Boolean(string='Reverse Chart')
    # Chart style
    chart_background_color = fields.Char(string='Background Color', default='#fff')
    chart_fore_color = fields.Char(string='Text Color', default="#373d3f")
    fill_type = fields.Selection([('solid', 'Solid'), ('gradient', 'Gradient'), ('pattern', 'Pattern')],
                                 default='solid')
    gradient_shade = fields.Selection([('light', 'Light'), ('dark', 'Dark')], default='light')
    gradient_type = fields.Selection(
        [('horizontal', 'Horizontal'), ('vertical', 'Vertical'), ('diagonal1', 'Diagonal-1'),
         ('diagonal2', 'Diagonal-2')], default='horizontal')

    pattern_type = fields.Selection(
        [('verticalLines', 'Vertical Lines'), ('horizontalLines', 'Horizontal'),
         ('slantedLines', 'Slanted Lines'), ('squares', 'Squares'), ('circles', 'Circles')], default='verticalLines')
    # Chart Animation
    is_enable_animation = fields.Boolean(string='Enable Animation', default=True)
    animation_easing_type = fields.Selection(
        [('linear', 'Linear'), ('easein', 'Ease In'), ('easeout', 'EaseOut'), ('easeinout', 'EaseInOut')],
        default='linear')
    animation_speed = fields.Integer(string="Animation Speed", default=800)
    is_enable_animation_gradually = fields.Boolean(string='Gradually animate one by one')
    animation_gradually_delay = fields.Integer(string='Animation Gradually Delay', default=150)
    # dashboard position use for items gridstack positions
    chart_dashboard_positions = fields.Char(string='chart Dashboard Position')

    @api.model
    def create(self, vals_list):
        res = super(EgCustomDashboardItem, self).create(vals_list)
        return res

    @api.onchange('record_sort_field', 'record_sort', 'record_sort_field', 'filter_domain')
    def _onchange_filter_record_configuration(self):
        if self.name != False:
            raise ValidationError(_(
                "Only Record limit are supported if you use another operation like sorting, domain so upgrade to pro version!!!"))

    @api.onchange('date_record_filter_type')
    def _onchange_date_record_filter_type(self):
        if self.date_record_filter_type != False and self.date_record_filter_type not in ['none', 'this_week',
                                                                                          'this_month']:
            raise ValidationError(_(
                "Date Filter Support Only This week and This Month if You use Another filter so upgrade for Dashboard Pro"))

    @api.onchange('is_show_grid', 'is_enable_animation', 'fill_type', 'is_chart_zoom', 'is_reserved_chart',
                  'is_show_datalabels', 'is_show_legend', 'stork_type', 'name_align_position')
    def _onchange_chart_theme(self):
        if self.name != False:
            raise ValidationError(_(
                "Only Chart Theme, Color Palette and Distributed Chart are supported if you use another theme configuration so update in Pro Version!!!"))

    @api.onchange('ir_model_id')
    def _onchange_ir_model_id(self):
        if self.ir_model_id:
            self.label_model_field_id = False
            self.measure_model_field_ids = False
            self.model_name = self.ir_model_id.model
            create_field_id = self.env['ir.model.fields'].search(
                [('name', '=', 'create_date'), ('model_id', '=', self.ir_model_id.id)])
            self.date_filter_field = create_field_id.id

    @api.onchange('chart_type')
    def _onchange_chart_type(self):
        if self.chart_type:
            self.label_model_field_id = False
            self.measure_model_field_ids = False
            if self.chart_type == 'tiles':
                self.chart_background_color = '#2778ee'
                self.chart_fore_color = '#fff'
                self.tile_image_type = 'default_icons'
                self.tile_icon = 'fa-line-chart'

    @api.depends('ir_model_id', 'label_model_field_id', 'date_record_filter_type', 'date_filter_field',
                 'measure_model_field_ids', 'record_limit')
    def _compute_chart_chart(self):
        for rec in self:
            if rec.ir_model_id:
                model_data_ids = self.env[rec.ir_model_id.model].search(
                    rec.filter_record(rec.date_record_filter_type, rec.date_filter_field), limit=rec.record_limit)
                if rec.ir_model_id and rec.measure_model_field_ids and rec.label_model_field_id:
                    if rec.chart_type in ['bar', 'column']:
                        measure_data_list = []
                        model_label_list = []
                        for measure_model_field_id in rec.measure_model_field_ids:
                            data_list = []
                            for model_data_id in model_data_ids:
                                data_list.append(model_data_id[measure_model_field_id.name])
                                if rec.label_model_field_id.ttype == 'datetime':
                                    date_time = model_data_id[rec.label_model_field_id.name].strftime(
                                        DEFAULT_SERVER_DATETIME_FORMAT)
                                    model_label_list.append(date_time)
                                elif rec.label_model_field_id.ttype == 'date':
                                    date_time = model_data_id[rec.label_model_field_id.name].strftime(
                                        DEFAULT_SERVER_DATE_FORMAT)
                                    model_label_list.append(date_time)
                                elif rec.label_model_field_id.ttype == 'many2one':
                                    name = model_data_id[rec.label_model_field_id.name].name
                                    model_label_list.append(name)
                                else:
                                    model_label_list.append(model_data_id[rec.label_model_field_id.name])
                            data_dict = {
                                'name': measure_model_field_id.field_description,
                                'data': data_list
                            }
                            measure_data_list.append(data_dict)
                        return_dict = {
                            'data_list': measure_data_list,
                            'model_label_list': model_label_list,
                        }
                        rec.chart_data = json.dumps(return_dict)
                    elif rec.chart_type in ['pie']:
                        measure_data_list = []
                        model_label_list = []
                        for model_data_id in model_data_ids:
                            measure_data_list.append(model_data_id[rec.measure_model_field_ids[0].name])
                            if rec.label_model_field_id.ttype == 'datetime':
                                date_time = model_data_id[rec.label_model_field_id.name].strftime(
                                    DEFAULT_SERVER_DATETIME_FORMAT)
                                model_label_list.append(date_time)
                            elif rec.label_model_field_id.ttype == 'date':
                                date_time = model_data_id[rec.label_model_field_id.name].strftime(
                                    DEFAULT_SERVER_DATE_FORMAT)
                                model_label_list.append(date_time)
                            elif rec.label_model_field_id.ttype == 'many2one':
                                name = model_data_id[rec.label_model_field_id.name].name
                                model_label_list.append(name)
                            else:
                                model_label_list.append(model_data_id[rec.label_model_field_id.name])
                        return_dict = {
                            'data_list': measure_data_list,
                            'model_label_list': model_label_list,
                        }
                        rec.chart_data = json.dumps(return_dict)
                    else:
                        rec.chart_data = False
                elif rec.ir_model_id and rec.chart_type == 'tiles':
                    if rec.calculation_type == 'sum' and rec.measure_model_field_ids:
                        total = 0
                        for model_data_id in model_data_ids:
                            total += model_data_id[rec.measure_model_field_ids[0].name]
                        return_dict = {
                            'total': format(total, '.2f')
                        }
                        rec.chart_data = json.dumps(return_dict)
                    elif rec.calculation_type == 'count':
                        record_count = len(model_data_ids.ids)
                        return_dict = {
                            'total': record_count,
                        }
                        rec.chart_data = json.dumps(return_dict)
                    else:
                        return_dict = {
                            'total': 0,
                        }
                        rec.chart_data = json.dumps(return_dict)
                else:
                    rec.chart_data = False
            else:
                rec.chart_data = False

    def filter_record(self, date_record_filter_type=None, date_filter_field=None):
        if date_record_filter_type in ['none']:
            date_filter_list = []
            return date_filter_list
        else:
            today_datetime = fields.Datetime.now()
            date_filter_list = []
            if date_record_filter_type == 'this_week':
                date_filter_list.append((date_filter_field.name, '>=', date_utils.start_of(today_datetime, 'week')))
                date_filter_list.append((date_filter_field.name, '<=', date_utils.end_of(today_datetime, 'week')))
            elif date_record_filter_type == 'this_month':
                date_filter_list.append((date_filter_field.name, '>=', date_utils.start_of(today_datetime, 'month')))
                date_filter_list.append((date_filter_field.name, '<=', date_utils.end_of(today_datetime, 'month')))
            return date_filter_list

    def calculate_aspect(self, width, height):
        def gcd(a, b):
            """The GCD (greatest common divisor) is the highest number that evenly divides both width and height."""
            return a if b == 0 else gcd(b, a % b)

        r = gcd(width, height)
        x = int(width / r)
        y = int(height / r)

        return f"{x}:{y}"
