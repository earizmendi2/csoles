/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Field } from "@web/views/fields/field";
import { View } from "@web/views/view";
import { ViewCompiler, getModifier } from "@web/views/view_compiler";
import { useService } from "@web/core/utils/hooks";

// Almacenamos los datos de perfil globalmente para que estén disponibles
let profileFieldsData = null;
let profileFieldsM2xData = null;

async function loadProfileFields(orm,modelName) {
    if (!profileFieldsData || !profileFieldsM2xData) {
        const allFields = await orm.call('res.users', 'get_profile_fields');
        if(allFields.normal_fields){
            profileFieldsData = allFields.normal_fields
        }
        if(allFields.m2x_fields){
            profileFieldsM2xData = allFields.m2x_fields
        }
    }
}

export function applyFieldOptions(sourceObj, targetObj, optionsMap) {
    Object.keys(optionsMap).forEach(key => {
        if (sourceObj[key]) {
            targetObj[optionsMap[key]] = key === 'is_invisible' ? "True" : true;
            if (key === 'is_invisible' && sourceObj[key]) {
                targetObj.column_invisible = "True";
            }
        }
    });

    return targetObj;
}

patch(View.prototype, {
    async setup() {
        super.setup();
        this.orm = useService("orm");
        if (this.orm && this.props.resModel){
            await loadProfileFields(this.orm,this.props.resModel);
        }
    },
});

patch(ViewCompiler.prototype, {
    compileNode(node, params = {}, evalInvisible = true) {
         if(node.nodeType === 1){
            const fieldProfile = profileFieldsData?.find(field => field.field_name === getModifier(node,"name"));
            if (fieldProfile && fieldProfile.is_invisible) {
                return;
            }
        }        
        return super.compileNode(node,params,evalInvisible);
    }
});

patch(Field, {
    parseFieldNode(node, models, modelName, viewType, jsClass) {
        let parsedField = super.parseFieldNode(node, models,modelName, viewType, jsClass);
        const fieldProfile = profileFieldsData?.find(field => 
            field.field_name === node.getAttribute("name") && field.model_name === modelName
        );
        
        const fieldM2xProfile = profileFieldsM2xData?.find(field => 
            field.field_name === node.getAttribute("name") && field.model_name === modelName
        );

        if (fieldProfile) {
            const profileOptionsMap = {
                is_required: 'required',
                is_invisible: 'invisible',
                is_readonly: 'readonly'
            };
        
            parsedField = applyFieldOptions(fieldProfile, parsedField, profileOptionsMap);
        }
        
        if (fieldM2xProfile) {
            const m2xOptionsMap = {
                no_open: 'no_open',
                no_create: 'no_create',
                no_create_edit: 'no_create_edit',
                no_quick_create: 'no_quick_create'
            };
        
            parsedField.options = applyFieldOptions(fieldM2xProfile, parsedField.options, m2xOptionsMap);
        }
        return parsedField;
    },
});
