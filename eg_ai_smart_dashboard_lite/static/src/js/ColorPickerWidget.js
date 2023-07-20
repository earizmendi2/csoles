odoo.define('eg_ai_smart_dashboard_lite.ColorPickerWidget', function (require) {
    "use strict";

    require('web.dom_ready');

    var registry = require('web.field_registry');
    var AbstractField = require('web.AbstractField');
    var core = require('web.core');
    var QWeb = core.qweb;

    var ColorPickerWidget = AbstractField.extend({
        supportedFieldTypes: ['char'],

         events: _.extend({}, AbstractField.prototype.events, {
            'change.spectrum .color_picker_input': '_color_picker_input_change',
        }),

        init: function (parent, state, params) {
            this._super.apply(this, arguments);
        },

        _render: function () {
            this.$el.empty();
            var default_color_value = '#376CAE';
            if (this.value) {
                default_color_value = this.value.split(',')[0];
            };
            var $view = $(QWeb.render('ColorPickerWidget'));
            this.$el.append($view)
            this.$el.find(".color_picker_input").spectrum({
                color: default_color_value,
                showInput: true,
                hideAfterPaletteSelect: true,
                showPaletteOnly: true,
                togglePaletteOnly: true,
                togglePaletteMoreText: 'More',
                togglePaletteLessText: 'Less',
                palette: [
                    ["#000","#444","#666","#999","#ccc","#eee","#f3f3f3","#fff"],
                    ["#f00","#f90","#ff0","#0f0","#0ff","#00f","#90f","#f0f"],
                    ["#f4cccc","#fce5cd","#fff2cc","#d9ead3","#d0e0e3","#cfe2f3","#d9d2e9","#ead1dc"],
                    ["#ea9999","#f9cb9c","#ffe599","#b6d7a8","#a2c4c9","#9fc5e8","#b4a7d6","#d5a6bd"],
                    ["#e06666","#f6b26b","#ffd966","#93c47d","#76a5af","#6fa8dc","#8e7cc3","#c27ba0"],
                    ["#c00","#e69138","#f1c232","#6aa84f","#45818e","#3d85c6","#674ea7","#a64d79"],
                    ["#900","#b45f06","#bf9000","#38761d","#134f5c","#0b5394","#351c75","#741b47"],
                    ["#600","#783f04","#7f6000","#274e13","#0c343d","#073763","#20124d","#4c1130"]
                ],
                clickoutFiresChange: true,
                showInitial: true,
                preferredFormat: "rgb",
            });

            if (this.mode === 'readonly') {
                this.$el.find('.color_picker_input').spectrum("disable");
            }
            else {
                this.$el.find('.color_picker_input').spectrum("enable");
            }
        },

        _color_picker_input_change: function (e, tinycolor) {
            this._setValue(tinycolor.toHexString());
        },
    });
    registry.add('chart_color_picker', ColorPickerWidget);
    return {
        ColorPickerWidget: ColorPickerWidget
    };
});
