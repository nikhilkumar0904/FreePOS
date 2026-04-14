/** @odoo-module **/
/**
 * FRCS B2B Dialog
 * ---------------
 * Pops up before finalising a payment when the cashier wants to issue a
 * B2B fiscal invoice.  Captures:
 *   - Buyer TIN  (mandatory for B2B — printed on the fiscal receipt)
 *   - Buyer Cost Centre (optional — reserved for future FRCS use)
 *
 * Pre-fills the TIN from the customer's VAT field if one is set on the
 * Odoo partner record.
 */
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { Dialog } from "@web/core/dialog/dialog";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

// ---------------------------------------------------------------------------
// B2BDialog component
// ---------------------------------------------------------------------------
export class FrcsB2BDialog extends Component {
    static template = "custom_pos.FrcsB2BDialog";
    static components = { Dialog };
    static props = {
        prefillTin: { type: String, optional: true },
        close: Function,
    };

    setup() {
        this.state = useState({
            tin: this.props.prefillTin || "",
            costCenter: "",
            error: "",
        });
    }

    onConfirm() {
        const tin = (this.state.tin || "").trim();
        if (!tin) {
            this.state.error = "Buyer TIN is required for a B2B transaction.";
            return;
        }
        this.props.close({ tin, costCenter: (this.state.costCenter || "").trim() });
    }

    onSkip() {
        // Cashier chose not to add B2B info — proceed as B2C
        this.props.close(null);
    }
}

// ---------------------------------------------------------------------------
// Patch PosOrder — store / restore B2B fields
// ---------------------------------------------------------------------------
patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        this.buyer_tin = vals.buyer_tin || null;
        this.buyer_cost_center = vals.buyer_cost_center || null;
    },

    setBuyerTin(tin) { this.buyer_tin = tin || null; },
    setBuyerCostCenter(cc) { this.buyer_cost_center = cc || null; },

    serialize() {
        const data = super.serialize(...arguments);
        if (this.buyer_tin) data.buyer_tin = this.buyer_tin;
        if (this.buyer_cost_center) data.buyer_cost_center = this.buyer_cost_center;
        return data;
    },
});

// ---------------------------------------------------------------------------
// Patch PaymentScreen — add B2B button + inject into _finalizeValidation
// ---------------------------------------------------------------------------
patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = useService("dialog");
    },

    /**
     * Open the B2B dialog.  Returns {tin, costCenter} on confirm, null on skip.
     */
    async _showB2BDialog() {
        const order = this.currentOrder;
        const partner = order?.get_partner?.();
        const prefillTin = partner?.vat || "";

        return new Promise((resolve) => {
            this.dialog.add(FrcsB2BDialog, {
                prefillTin,
                close: (result) => resolve(result),
            });
        });
    },

    /**
     * "B2B Invoice" button handler — opens dialog and stores result on order.
     */
    async onClickB2B() {
        const result = await this._showB2BDialog();
        if (result) {
            this.currentOrder.setBuyerTin(result.tin);
            this.currentOrder.setBuyerCostCenter(result.costCenter);
            this.notification.add(
                `B2B: TIN ${result.tin}${result.costCenter ? " | CC " + result.costCenter : ""} set.`,
                { type: "success" }
            );
        } else {
            // Cleared
            this.currentOrder.setBuyerTin(null);
            this.currentOrder.setBuyerCostCenter(null);
        }
    },
});
