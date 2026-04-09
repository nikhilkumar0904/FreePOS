import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { ActionpadWidget } from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import { _t } from "@web/core/l10n/translation";

const DEFAULT_LABEL = ["G"];
const INVOICE_LABELS = {
    NS: "Normal Sale",
    NR: "Normal Refund",
    AS: "Advance Sale",
    AR: "Advance Refund",
    CS: "Copy Sale",
    CR: "Copy Refund",
    TS: "Training Sale",
    TR: "Training Refund",
    PS: "Proforma Sale",
    PR: "Proforma Refund",
};
patch (TicketScreen.prototype, {

    _notify(message, type = "info") {
        const svc = this.notification || this.env.services?.notification;
        if (svc) {
            svc.add(message, { type });
        } else {
            console.warn("Notification service unavailable", message);
        }
    },

    _normalizeLabel(order) {
        return (order?.invoice_label || "").trim().toUpperCase();
    },

    _isAdvance(order) {
        const label = this._normalizeLabel(order);
        return ["AS", "ADVANCE SALE", "ADVANCE"].includes(label);
    },

    _isProforma(order) {
        const label = this._normalizeLabel(order);
        return ["PS", "PROFORMA SALE", "PROFORMA"].includes(label);
    },

    _isAdvanceOrProforma(order) {
        return this._isAdvance(order) || this._isProforma(order);
    },

    getSecondaryActionName() {
        const order = this.getSelectedOrder();
        if (this._isAdvanceOrProforma(order)) {
            return _t("Process Sale");
        }
        return _t("Reprint");
    },

    getSecondaryActionHandler() {
        const order = this.getSelectedOrder();
        if (this._isAdvanceOrProforma(order)) {
            return () => this.onProcessSale();
        }
        return () => this.onReprint();
    },

    getCashier(order) {
        return order.user_id?.name;
    },

    getInvoiceLabel(order) {
        const raw = order?.invoice_label;
        if (!raw || String(raw).toUpperCase() === "NULL") {
            return "";
        }
        const code = String(raw).trim().toUpperCase();
        return INVOICE_LABELS[code] || code || "";
    },

    async onReprint() {
        const order = this.getSelectedOrder();
        const isRefund = order?.getHasRefundLines?.() || false;

        console.log("COPY RFUNNDDDDD" + isRefund);

        if (!order) {
            this.notification.add(
                this.env._t("Select an order first"), 
                { type: "warning" }
            );

            return;
        }

        //Prepare payload to send to TaxCore
        const invoiceId = await this.pos.data.call (
            "pos.order.fiscal.record",
            "get_invoice_number",
            [order.id]
        );

        const referentDocumentDT = await this.pos.data.call (
            "pos.order.fiscal.record",
            "get_created_time",
            [order.id]
        );

        if (!invoiceId) {
            this.notification.add (
                this.env._t("No stored fiscal payload for this order"),
                {type: danger}
            );

            return;
        }

        const sdcInvoice = await this.pos.data.call (
            "pos.order.fiscal.record",
            "get_sdc_invoice",
            [order.id]
        )

        const invoiceType = ["Normal", "Refund", "Copy", "Training", "Proforma", "Advance"];
        const transactionType = ["Sale", "Refund"];
        let transaction_type;
        let invoice_type;


        if (isRefund){
            invoice_type = invoiceType[2];
            transaction_type = transactionType[1];
        } else {
            invoice_type = invoiceType[2];
            transaction_type = transactionType[0];
        }

        let invoicePayload;

        const items = await Promise.all(
            order.get_orderlines().map(async (line) => {
                const taxLabel = await this.pos.data.call(
                    "pos.order.fiscal.record",
                    "get_tax_label",
                    [line.get_product()?.id]
                );

                const labels = taxLabel ? [taxLabel] : DEFAULT_LABEL.slice();
                console.log("TAXXXXXX LABELLSLS" + labels)
                let quantity = line.get_quantity();
                const discount = line.get_discount();

                if (transaction_type === transactionType[1]) {
                    quantity = Math.abs(quantity);
                }

                return {
                    GTIN: line.product?.barcode || null,
                    Name: line.get_full_product_name() || "Item",
                    Quantity: quantity,
                    Discount: discount,
                    Labels: labels,
                    unitPrice: line.get_price_with_tax(),
                    TotalAmount: Math.abs(line.get_price_with_tax()),
                };
            })
        );


        const paymentTypes = order.payment_ids.map((line)=> {
            const method = line.payment_method_id;
            const methodName = (method.name || "").toLowerCase();
            let type = "Card";
            if (method.type === "cash" || methodName.includes("cash")) {
                type = "Cash";
            } else if (methodName.includes("mobile")) {
                type = "MobileMoney";
            } else {
                type = "Card";
            }

            return {
                Amount: line.get_amount(),
                PaymentType: type,

            };
        });




        try{

            invoicePayload = {
                DateAndTimeOfIssue: new Date().toISOString(),
                Cashier: this.pos.get_cashier().name,
                BD: null,
                BuyerCostCenterId: null,
                invoiceType: invoice_type,
                transactionType: transaction_type,
                payment: paymentTypes,
                InvoiceNumber: "22222",
                ReferentDocumentNumber: sdcInvoice,
                ReferentDocumentDT: referentDocumentDT,
                Options: {
                    OmitTextualRepresentation: 0,
                    OmitQRCodeGen: 0,
                },
                Items: items,
            };

        } catch (err) {
            console.error("Taxcore validation failed: ", err);
        } 

        let taxcoreResponse;
        try {
            taxcoreResponse = await this.pos.data.call("taxcore.client", "send_invoice_v3", [invoicePayload]);
            console.log("TaxCore response", taxcoreResponse);
        } catch (error) {
            console.error("TaxCore RPC failed", error);
            this.notification.add(
                _t("Failed to sign invoice with TaxCore: %s", error.message || error),
                { type: "danger" }
            );
            return; 
        }
        if (!taxcoreResponse || !taxcoreResponse.invoiceNumber) {
            console.error("TaxCore returned no SDC Invoice Number", taxcoreResponse);
            this.notification.add(_t("No SDC Invoice returned by TaxCore; order not saved."), { type: "danger" });
            return;
        }
        order.setTaxCoreResponse(taxcoreResponse);

        if (this.pos.get_order().uuid !== order.uuid) {
            this.pos.set_order(order);
        }

        this.pos.showScreen("ReceiptScreen");



    },

    async onProcessSale() {
        const order = this.getSelectedOrder();
        if (!order) {
            this._notify(_t("Select an order first."), "warning");
            return;
        }
        if (!this._isAdvanceOrProforma(order)) {
            this._notify(_t("Only advance or proforma sales can be processed."), "warning");
            return;
        }
        const sdcInvoice = await this.pos.data.call(
            "pos.order.fiscal.record",
            "get_sdc_invoice",
            [order.id]
        );
        if (!sdcInvoice) {
            this._notify(_t("No SDC invoice linked to this order."), "warning");
            return;
        }
        const referentDt = await this.pos.data.call(
            "pos.order.fiscal.record",
            "get_created_time",
            [order.id]
        );

        const newOrder = this.pos.add_new_order();
        this.pos.set_order(newOrder);
        const partner = order.get_partner?.();
        if (partner) {
            newOrder.set_partner(partner);
        }
        for (const line of order.get_orderlines()) {
            const product = line.get_product?.();
            if (!product) {
                continue;
            }
            const qty = line.get_quantity?.() || 0;
            if (!qty) {
                continue;
            }
            await this.pos.addLineToOrder(
                {
                    product_id: product,
                    qty,
                    price_unit: line.get_unit_price?.() ?? undefined,
                    discount: line.get_discount?.() ?? 0,
                },
                newOrder,
                {},
                false
            );
        }
        const referenceKind = this._isAdvance(order) ? "advance" : "proforma";

        newOrder.setReferenceDocument?.({
            number: sdcInvoice,
            datetime: referentDt,
            source_invoice_label: order.invoice_label,
            source_order_id: order.id,
            kind: referenceKind,
        });
        this.pos.proformaMode = false;
        this.pos.trainingMode = false;
        this.pos.advanceMode = false;
        localStorage.setItem("pos_proforma_mode", JSON.stringify(false));
        localStorage.setItem("pos_training_mode", JSON.stringify(false));
        localStorage.setItem("pos_advance_mode", JSON.stringify(false));
        newOrder.setProcessingLock?.(true);
        newOrder.setIsProforma?.(false);
        newOrder.setIsAdvance?.(false);
        newOrder.setIsTraining?.(false);
        this._notify(
            _t("Reference attached. Complete the sale normally to finalize."),
            "success"
        );
        this.pos.showScreen("ProductScreen");
    },

});

patch (ActionpadWidget.prototype, {

    setup(){
        super.setup(...arguments);
        this.secondaryActionEnabled = typeof this.props.secondaryActionToTrigger === "function";
    },

});

patch(ProductScreen.prototype, {
    async addProductToOrder() {
        const order = this.pos.get_order();
        if (order?.isProcessingLocked?.()) {
            this.notification.add(
                _t("Cannot add products while processing this sale."),
                { type: "warning" }
            );
            return;
        }
        return await super.addProductToOrder(...arguments);
    },
});

patch(ActionpadWidget, {
    props: {
        ...ActionpadWidget.props,
        secondaryActionName: { type: String, optional: true},
        secondaryActionToTrigger: {type: Function, optional: true},
    },
});
