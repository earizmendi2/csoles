odoo.define('eg_ai_smart_dashboard_lite.graph_preview', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var QWeb = core.qweb;
    var registry = require('web.field_registry');
    var field_utils = require('web.field_utils');
    var session = require('web.session');

    var GraphPreview = AbstractField.extend({
        supportedFieldTypes: ['char'],
        resetOnAnyFieldChange: true,

        init: function (parent, state, params) {
            this.supported_chart = ['bar','pie','column','tiles'];
            return this._super.apply(this, arguments);
        },

        willStart: function () {
            var self = this;
            var defs = [this._super.apply(this, arguments)];
            core.bus.on("DOM_updated", this, function () {
                if(self.shouldRenderChart && $.find('#custom-chart-preview').length>0) self._getChartData();
            });
            return Promise.all(defs);
        },

        isSet: function () {
            return true;
        },

        _render: function(){
            this.shouldRenderChart = true;
            this.$el.empty()
            if(this.recordData.ir_model_id){
                if (!this.supported_chart.includes(this.recordData.chart_type)){
                    this.$el.append($('<div style="color:red;">').text("Supported Chart only Pie, Column, Bar and Tiles if you use another chart so upgrade to Pro Version"));
                }
                else if (this.recordData.chart_type == 'tiles'){
                    if (this.recordData.chart_data){
                        this._generate_tiles();
                    }
                }
                else if  (this.recordData.measure_model_field_ids){
                    if(this.recordData.label_model_field_id){
                        if (this.recordData.chart_data){
                            this._getChartData();
                        }
                    }
                    else{
                        this.$el.append($('<div>').text("Measure field and Label Model field are required for create Chart"));
                    }
                }
                else{
                    this.$el.append($('<div>').text("Measure field and Label Model field are required for create Chart"));
                }
            }
            else{
                this.$el.append($('<div>').text("Please select a Model Name!"));
            }
            return Promise.resolve();
        },

        _generate_tiles: function(){
            var self = this;
            var image_src = session.url('/web/image', {
                model: self.model,
                id: JSON.stringify(self.res_id),
                field: "tile_image_selection",
                unique: field_utils.format.datetime(self.recordData.__last_update).replace(/[^0-9]/g, ''),
            });
            var dataset = JSON.parse(self.recordData.chart_data)

            var $chartContainer = $(QWeb.render('DashboardTilePreview', {
                'background_color':self.recordData.chart_background_color,
                'text_color': self.recordData.chart_fore_color,
                'title':  self.recordData.name,
                'tile_image_type': self.recordData.tile_image_type,
                'fa_icon_name': self.recordData.tile_icon,
                'image_url': image_src,
                'id': self.recordData.id,
                'value': dataset.total,
            }));
            this.$el.append($chartContainer);
        },

        _getChartData: function(){
            var self = this;
            if (self.shouldRenderChart){
                var $chartContainer = this.$el.html(QWeb.render('custom_graph_preview_qweb'));
            }
            if($.find('#custom-chart-preview').length > 0){
               this.generate_chart_options();
            }
        },

        generate_chart_options: function(){
            var self = this;
            var fields = self.recordData
            var dataset = JSON.parse(fields.chart_data)
            var options = {
                series: dataset.data_list,
                chart: {
                    toolbar: {
                        show: false
                    },
                    type: self.set_chart_type(),
                    height: 350,
                    background: fields.chart_theme == 'custom' ? fields.chart_background_color : false,
                    foreColor: fields.chart_theme == 'custom' ? fields.chart_fore_color : false,
                    redrawOnParentResize: true,
                    redrawOnWindowResize: true,
                },
                title: {
                    text: fields.name,
                },
                theme: {
                    mode: fields.chart_theme == 'custom' ? false : fields.chart_theme,
                    palette: fields.color_palette,
                },
            };

            if (self.recordData.chart_type == 'bar' || self.recordData.chart_type == 'column'){
                options['xaxis'] = {
                    categories: dataset.model_label_list,
                }
                if (self.recordData.chart_type == 'bar'){
                    options['plotOptions'] =  {
                        bar: {
                            horizontal: true,
                            columnWidth: '55%',
                            distributed: self.recordData.is_distributed_chart,
                        }
                    }
                }
                else{
                    options['plotOptions'] = {
                        bar: {
                            horizontal: false,
                            columnWidth: '55%',
                            distributed: self.recordData.is_distributed_chart,
                        }
                    }
                }
            }
            else if (self.recordData.chart_type == 'pie'){
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
            var chart = new ApexCharts($.find('#custom-chart-preview')[0], options);
            chart.render();
        },

        set_chart_type: function(){
            var self = this;
            var chart_type;
            if (self.recordData.chart_type == 'column'){
                chart_type = 'bar'
            }
            else{
                chart_type = self.recordData.chart_type
            }
            return chart_type;
        },


    });
    registry.add('custom_graph_preview', GraphPreview);

    return {
        GraphPreview: GraphPreview,
    };

});
