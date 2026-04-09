/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype,{

    addLineToCurrentOrder(vals, opt ={}, configure=true){
        const currentOrder = this.get_order();
        if (currentOrder?.getHasRefundLines()){
            this.dialog.add(ConfirmationDialog, {
                title: _t("Refund in Progress"),
                body: _t("You cannot add new products while processing a refund."),
                confirmLabel: _t("OK"),
            })
            return null;
        }

        return super.addLineToCurrentOrder(...arguments);

    },

});