odoo.define('eg_ai_smart_dashboard_lite.DashboardIconPicker', function (require) {
    "use strict";

    require('web.dom_ready');

    var registry = require('web.field_registry');
    var AbstractField = require('web.AbstractField');
    var fields = require('web.basic_fields');
    var core = require('web.core');
    var QWeb = core.qweb;

    var DashboardIconPicker = fields.FieldChar.extend({
        template: 'DashboardIconPicker',
        widget_class: 'oe_form_field_color',

        events: _.extend({}, AbstractField.prototype.events, {
            'change .color_picker_input': '_color_picker_input_change',
        }),

        _renderReadonly: function () {
            var show_value = this._formatValue(this.value);
            this.$el.text(show_value);
        },

        _getValue: function () {
            var $input = this.$el.find('input');
            var val = $input.val();
            return $input.val();
        },

        init: function (parent, state, params) {
            this._super.apply(this, arguments);
        },

        _color_picker_input_change: function (e, tinycolor) {
            this._setValue(this.$el.find('.color_picker_input').val());
        },

        _renderEdit: function () {
            var show_value = this.value ;
            var $input = this.$el.find('input');
            $input.val(show_value);

            var name = this.$el.find('input').iconpicker(this.$el.find('input'));
            this.$input = $input;
        },

    });

    registry.add('dashboard_icon_picker', DashboardIconPicker);
    return {
        DashboardIconPicker: DashboardIconPicker
    };

});
