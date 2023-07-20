odoo.define('eg_ai_smart_dashboard_lite.dashboard_board', function (require) {
"use strict";
    var AbstractAction = require('web.AbstractAction');
    var rpc = require('web.rpc');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var viewRegistry = require('web.view_registry');
    var _t = core._t;
    var QWeb = core.qweb;
    var utils = require('web.utils');
    var session = require('web.session');
    var Widget = require('web.Widget');
    var ajax = require('web.ajax');

    var CustomDashboardBoard =  AbstractAction.extend({
        contentTemplate: 'CustomDashboardBoard',

        events: {
            'click #save_dashboard': 'save_dashboard_data',
            'click #chart-type-selection > span': 'add_chart_item',
            'click #edit_dashboard': 'edit_dashboard',
            'click #search-button': 'search_chart',
            'click #searchclear': 'clear_search',
            'click .delete-item-chart': 'delete_chart_item',
            'click .edit-item-chart': 'edit_item_chart',
        },

        init: function(parent, action) {
            var self= this;
            if (action.context.active_id){
                self.dashboard_board_id = action.context.active_id;
            }
            else{
               self.dashboard_board_id = action.params.dashboard_board_id;
            }
            this.supported_charts = ['bar','pie','column','tiles'];
            this._super.apply(this, arguments);
        },

        willStart: function () {
            var self = this;
            var def = this._rpc({
                    model: 'custom.dashboard.board',
                    method: 'get_dashboard_items_lines',
                    args: [self.dashboard_board_id],
                })
                .then(function (res) {
                     self.dashboard_data = res;
                });

            return Promise.all([
                this._super.apply(this, arguments),def
            ]);
        },

        start: function () {
            var self = this;
            var options = {};
            self._render_chart();
            return this._super();
        },

        add_chart_item: function(event){
            var self = this;
            console.log(event.currentTarget);
            var chart_type = event.currentTarget.dataset.chartType;
            var options = {
                on_close: function () {
                    ajax.jsonRpc("/custom_dashboard/update_chart_item_dashboard", 'call', {'dashboard_id': self.dashboard_board_id})
                    .then(function(res){
                        self.do_action(res);
                    });
                },
            };
            self.do_action({
                type: 'ir.actions.act_window',
                res_model: 'eg.custom.dashboard.item',
                view_id: 'custom_dashboard_form_view',
                views: [
                    [false, 'form']
                ],
                target: 'new',
                context: {
                    'custom_dashboard_board_id': self.dashboard_board_id,
                    'chart_type': chart_type,
                    'form_view_ref': 'eg_custom_dashboard_item_form_view',
                    'form_view_initial_mode': 'edit',
                },
            },options);
        },

        clear_search: function(){
            var self = this;
            self.$("#search-input-chart").val('');
            ajax.jsonRpc("/custom_dashboard/remove_search_chart", 'call', {'dashboard_item_id': self.dashboard_board_id})
            .then(function(res){
               self.$(".grid-stack").remove();
                self.$(".container-fluid-dashboard").append("<div class='grid-stack' id='grid-stack'></div>")
                self.dashboard_data = res;
                self._render_chart();
            });
        },

        change_chart_search: function(){
            var self = this;
            var search_input = self.$("#search-input-chart").val();
            ajax.jsonRpc("/custom_dashboard/search_input_chart", 'call', {'search_input': search_input, 'dashboard_item_id': self.dashboard_board_id})
            .then(function(res){
                self.$(".grid-stack").remove();
                self.$(".container-fluid-dashboard").append("<div class='grid-stack' id='grid-stack'></div>")
                self.dashboard_data = res;
                self._render_chart();
            });
        },

        search_chart: function(){
            var self = this;
            var search_input = self.$("#search-input-chart").val();
            ajax.jsonRpc("/custom_dashboard/search_input_chart", 'call', {'search_input': search_input, 'dashboard_item_id': self.dashboard_board_id})
            .then(function(res){
                self.$(".grid-stack").remove();
                self.$(".container-fluid-dashboard").append("<div class='grid-stack' id='grid-stack'></div>")
                self.dashboard_data = res;
                self._render_chart();
            });
        },

        save_dashboard_data: function(event){
            var self = this;
            self.grid.enableMove(false, true);
            self.grid.enableResize(false, true);
            var data_list = []
            self.$('.chart-container').each(function(){
                var data_obj = {
                    'item_id': this.getAttribute('data-gs-id'),
                    'chart_height': parseFloat(this.getAttribute('data-gs-height')),
                    'chart_width': parseFloat(this.getAttribute('data-gs-width')),
                    'chart_x': parseFloat(this.getAttribute('data-gs-x')),
                    'chart_y': parseFloat(this.getAttribute('data-gs-y')),
                }
                data_obj.item_id = parseFloat(data_obj.item_id.slice(11))
                data_list.push(data_obj);
            })
            ajax.jsonRpc("/custom_dashboard/dashboard_configuration", 'call', {'data_list': JSON.stringify(data_list)})
            self.$(event.target).hide();
            self.$("#edit_dashboard").show();
            self.$("#dashboard_template_name").show();
            self.$("#dashboard_template_name_input").hide();
            var dashboard_template_name = self.$('#dashboard_template_name_input').val();
            ajax.jsonRpc("/custom_dashboard/dashboard_template_name", 'call', {'dashboard_id': self.dashboard_board_id, 'template_name': dashboard_template_name})
            .then(function(result){
                self.$("#dashboard_template_name").text(result);
                self.$("#dashboard_template_name_input").val(result);
            });
        },

        edit_dashboard: function(){
            var self = this;
            self.grid.enableMove(true, false);
            self.grid.enableResize(true, false);
            self.$(event.target).hide();
            self.$("#save_dashboard").show();
            self.$('#dashboard_template_name_input').show();
            self.$('#dashboard_template_name').hide();
        },

        _render_chart: function(){
            var self = this;
            var options = {};
            self.dashboard_data.dashboard_item_ids.forEach(function (dashboard_item_id) {
                ajax.jsonRpc("/custom_dashboard/get_dashboard_items_data", 'call', {'dashboard_item_id': dashboard_item_id})
                .then(function (res) {
                    if (!self.supported_charts.includes(res.chart_type)){
                        self.generate_tiles(res, dashboard_item_id, true);
                    }
                    else if (res.chart_type == 'tiles'){
                        self.generate_tiles(res, dashboard_item_id, false);
                    }
                    else{
                        self.generate_graph(res, dashboard_item_id);
                    }
                });
            });
        },

        generate_tiles: function(dict_data, dashboard_item_id,is_warning_tile){
            var self = this;
            var dataset = is_warning_tile ? false : JSON.parse(dict_data.chart_data)
//            var dataset = JSON.parse(dict_data.chart_data);
            var grid_path = null;
            var new_grid = null;
            var options_grid = {
                alwaysShowResizeHandle: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
                staticGrid: true,
                float: false,
                margin: '100px',
            };
            self.$('.grid-stack').gridstack(options_grid);
            var grid_stack = self.$('.grid-stack');
            self.grid = self.$('.grid-stack').data('gridstack');
            self.grid.enableMove(false, true);
            self.grid.enableResize(false, true);
            grid_stack.append(`<div class='chart-container box tile-box' id='chart_item_${dashboard_item_id}' /></div>`)
            var serizize_data = null;
            if (dict_data.chart_dashboard_positions){
                var dict_obj = JSON.parse((dict_data.chart_dashboard_positions))
                serizize_data = [{id: `chart_item_${dashboard_item_id}`, x: dict_obj.chart_x, y: dict_obj.chart_y, w: dict_obj.chart_width, h:dict_obj.chart_height,maxHeight:2, minHeight:2,minWidth:2}]
            }
            else{
                serizize_data = [{id: `chart_item_${dashboard_item_id}`, x: 0, y: 200, w: 3, h:4,maxHeight:2,minHeight:2,minWidth:2}]
            }
            var items = GridStackUI.Utils.sort(serizize_data);
            items.forEach(node=>{
                var containerElt = $("#" + node.id);
                containerElt.attr("data-gs-id", node.id);
                containerElt.attr("data-gs-width", node.w);
                containerElt.attr("data-gs-height", node.h);
                containerElt.attr("data-gs-x", node.x);
                containerElt.attr("data-gs-y", node.y);
                containerElt.attr("data-gs-max-height", node.maxHeight);
                containerElt.attr("data-gs-min-height", node.minHeight);
                containerElt.attr("data-gs-min-width", node.minWidth);
                grid_path = self.grid.makeWidget(containerElt)
            });
            var image_src = session.url('/web/image', {
                model: dict_data.model_name,
                id: dict_data.id,
                field: "tile_image_selection",
            });

            var $chartContainer = $(QWeb.render('DashboardTiles', {
                'background_color':dict_data.chart_background_color,
                'chart_type': dict_data.chart_type,
                'text_color': dict_data.chart_fore_color,
                'tile_image_type': dict_data.tile_image_type,
                'tile_icon': dict_data.tile_icon,
                'title':  dict_data.name,
                'image_url': image_src,
                'id': dict_data.id,
                'value': dataset.total,
                'is_warning_tile': is_warning_tile,
            }));
            var new_chart = self.$(".grid-stack").find(`[id='chart_item_${dashboard_item_id}']`)
            new_chart.append('<div class="grid-stack-item-content tile-shadow"></div>')
            var new_grid_item = self.$(".grid-stack").find(`[id='chart_item_${dashboard_item_id}']`).find('.grid-stack-item-content');
            new_grid_item.prepend($chartContainer);
        },

        generate_graph: function(dict_data, dashboard_item_id){
            var self = this;
            var dataset = JSON.parse(dict_data.chart_data);
            var grid_path = null;
            var new_grid = null;
            var options_grid = {
                alwaysShowResizeHandle: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent),
                staticGrid: true,
                float: false,
                margin: '100px',
            };
            self.$('.grid-stack').gridstack(options_grid);
            var grid_stack = self.$('.grid-stack');
            self.grid = self.$('.grid-stack').data('gridstack');
            self.grid.enableMove(false, true);
            self.grid.enableResize(false, true);
            grid_stack.append(`<div class='chart-container box' id='chart_item_${dashboard_item_id}' /></div>`)
            var serizize_data = null;
            if (dict_data.chart_dashboard_positions){
                var dict_obj = JSON.parse((dict_data.chart_dashboard_positions))
                serizize_data = [{id: `chart_item_${dashboard_item_id}`, x: dict_obj.chart_x, y: dict_obj.chart_y, w: dict_obj.chart_width, h:dict_obj.chart_height}]
            }
            else{
                serizize_data = [{id: `chart_item_${dashboard_item_id}`, x: 0, y: 200, w: 5, h:5}]
            }
            var items = GridStackUI.Utils.sort(serizize_data);
            items.forEach(node=>{
                var containerElt = $("#" + node.id);
                containerElt.attr("data-gs-id", node.id);
                containerElt.attr("data-gs-width", node.w);
                containerElt.attr("data-gs-height", node.h);
                containerElt.attr("data-gs-x", node.x);
                containerElt.attr("data-gs-y", node.y);
                grid_path = self.grid.makeWidget(containerElt)
            });

            var options = {
                series: dataset.data_list,
                chart: {
                    type: dict_data.chart_type == 'column'? 'bar': dict_data.chart_type,
                    height : '100%',
                    background: dict_data.chart_theme == 'custom' ? dict_data.chart_background_color : false,
                    foreColor: dict_data.chart_theme == 'custom' ? dict_data.chart_fore_color : false,
                    redrawOnParentResize: true,
                    redrawOnWindowResize: true,
                    toolbar: {
                        show: false
                    },
                },
                title: {
                    text: dict_data.name,
                },
                theme: {
                    mode: dict_data.chart_theme == 'custom' ? false : dict_data.chart_theme,
                    palette: dict_data.color_palette,
                },
            };
            if (dict_data.chart_type == 'bar' || dict_data.chart_type == 'column'){
                options['xaxis'] = {
                    categories: dataset.model_label_list,
                }
                options['plotOptions'] =  {
                    bar: {
                        horizontal: dict_data.chart_type == 'column'? false : true,
                        columnWidth: '55%',
                        distributed: dict_data.is_distributed_chart,
                    }
                }
            }
            else if (dict_data.chart_type == 'pie'){
                options['labels'] = dataset.model_label_list
                options['responsive'] = [{
                    breakpoint: 480,
                    options: {
                        chart: {
                            width: 200
                        },
                    }
                }]
            }
            var new_chart = self.$(".grid-stack").find(`[id='chart_item_${dashboard_item_id}']`)
            new_chart.append('<div class="grid-stack-item-content"></div>')
            var new_grid_item = self.$(".grid-stack").find(`[id='chart_item_${dashboard_item_id}']`).find('.grid-stack-item-content')
            var chart = new ApexCharts(new_grid_item[0], options);
            chart.render();
        },

        destroy: function () {
            this._super.apply(this, arguments);
        },

    });

    core.action_registry.add('custom_dashboard_client_action', CustomDashboardBoard);
    return {
        CustomDashboardBoard:  CustomDashboardBoard,
    };

});
