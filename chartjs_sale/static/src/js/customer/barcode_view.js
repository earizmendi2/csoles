odoo.define('customer.View', function (require) {
    'use strict';

    var AbstractView = require('web.AbstractView');
    var view_registry = require('web.view_registry');

    var CustomerController = require('customer.Controller');
    var CustomerModel = require('customer.Model');
    var CustomerRenderer = require('customer.Renderer');

    var CustomerView = AbstractView.extend({
        display_name: 'Customer',
        icon: 'fa-id-card-o',
        config: _.extend({}, AbstractView.prototype.config, {
            Model: CustomerModel,
            Controller: CustomerController,
            Renderer: CustomerRenderer,
        }),
        viewType: 'customer',
        searchMenuTypes: ['filter', 'favorite'],
        accesskey: "a",
        init: function (viewInfo, params) {
            this._super.apply(this, arguments);
        },
    });

    view_registry.add('customer', CustomerView);

    return CustomerView;

});