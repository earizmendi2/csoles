odoo.define('customer.Renderer', function (require) {
    'use strict';

    var AbstractRenderer = require('web.AbstractRenderer');
    var core = require('web.core');
    var qweb = core.qweb;

    var CustomerRenderer = AbstractRenderer.extend({
        events: _.extend({}, AbstractRenderer.prototype.events, {
            'click .o_primary_button': '_onClickButton',
        }),

        _render: function () {
            this.$el.empty();
            this.$el.append(qweb.render('ViewCustomer', { 'data_list': this.state }));
            return this._super.apply(this, arguments);
        },

        _onClickButton: function (ev) {

            ev.preventDefault();
            var target = $(ev.currentTarget);
            var customer_id = target.data('id');
            console.log(customer_id)
            this.trigger_up('view_customer', {
                'id': customer_id,
            });
        }
    });

    return CustomerRenderer;

});