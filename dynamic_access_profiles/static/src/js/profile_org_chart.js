/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ProfileOrgChart extends Component {
    static template = "dynamic_access_profiles.ProfileOrgChart";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
        onWillStart(() => this.load(this.props.record.resId));
        onWillUpdateProps((nextProps) => {
            if (nextProps.record.resId !== this.props.record.resId) {
                return this.load(nextProps.record.resId);
            }
        });
    }

    async load(profileId) {
        this.state.data = profileId
            ? await this.orm.call("res.profile", "get_profile_org_chart", [[profileId]])
            : null;
    }

    openProfile(profileId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.profile",
            res_id: profileId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("fields").add("profile_org_chart", {
    component: ProfileOrgChart,
    supportedTypes: ["many2one"],
});
