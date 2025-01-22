/** @odoo-module **/

import { ImageField } from '@web/views/fields/image/image_field';
import { useService } from "@web/core/utils/hooks";
import { patch } from 'web.utils';
import WebcamDialog from '@legion_webcam_image/js/webcam_dialog';


patch(ImageField.prototype, 'legion_webcam_image', {

    setup() {
        this._super(...arguments);
        this.dialogService = useService("dialog");
    },

    _openRearCamera(ev) {
        this.dialogService.add(WebcamDialog, {
            mode: true,
            onWebcamCallback: (data) => this.onWebcamCallback(data),
        });
    },

    async onWebcamCallback(base64) {
        this.props.update(base64)
    }

})
