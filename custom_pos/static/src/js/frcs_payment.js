/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { _t } from "@web/core/l10n/translation";


const DEFAULT_LABEL = ["G"];


// Sending data to TaxCore
patch(PaymentScreen.prototype, {

    async addNewPaymentLine(paymentMethod) {
        if (!paymentMethod) {
            return super.addNewPaymentLine(...arguments);
        }

        const methodName = (paymentMethod.name || "").toLowerCase();
        if (methodName === "proforma" && !this.pos.proformaMode) {
            this.notification.add(
                _t("Enable Proforma mode before using the Proforma payment method."),
                { type: "warning" }
            );
            return false;
        }
        if (methodName === "training" && !this.pos.trainingMode) {
            this.notification.add(
                _t("Enable Training mode before using the Training payment method."),
                { type: "warning" }
            );
            return false;
        }

        return await super.addNewPaymentLine(...arguments);
    },

    async onMounted(){
        await super.onMounted?.();

        if (this.pos.proformaMode) {
            await this._ensureProformaLine();
        }

        if (this.pos.trainingMode){
            await this._ensureTrainingLine();
        }

    },

    async _ensureProformaLine(){
        const order = this.currentOrder;
        if (!order) return;

        order.setIsProforma?.(true);

        const pm = this.pos.models["pos.payment.method"].find((m) =>
        m.name === "Proforma");

        if (!pm){
            this.notification.add(
                _t('Create a payment method named "Proforma" and add it to the POS config.'),
                { type: "warning"});

            return;
        }

        // Remove previous Proforma line
        for (const line of order.paymentlines || []) {
            if (line.payment_method?.id === pm.id) {
                order.remove_paymentline(line);
            }
        }

        // Add a line that equals current due
        const added = await this.addNewPaymentLine(pm);
        if (added) {
            const lines = order.paymentlines || [];
            const lastline = lines [lines.length -1];
            if(lastline){
                lastline.set_amount(order.get_total_with_tax() - order.get_rounding_applied());
            }
        }
    },

    async _ensureTrainingLine(){
        const order = this.currentOrder;
        if (!order) return;

        order.setIsTraining?.(true);

        const pm = this.pos.models["pos.payment.method"].find((m) =>
        m.name === "Training");

        if (!pm){
            this.notification.add(
                _t('Create a payment method named "Training" and add it to the POS config.'),
                { type: "warning"});

            return;
        }

        // Remove previous Training line
        for (const line of order.paymentlines || []) {
            if (line.payment_method?.id === pm.id) {
                order.remove_paymentline(line);
            }
        }

        // Add a line that equals current due
        const added = await this.addNewPaymentLine(pm);
        if (added) {
            const lines = order.paymentlines || [];
            const lastline = lines [lines.length -1];
            if(lastline){
                lastline.set_amount(order.get_total_with_tax() - order.get_rounding_applied());
            }
        }
    },


    async validateOrder(isForce) {
        if (this.pos.proformaMode) {
            await this._ensureProformaLine();
            this.currentOrder.setIsProforma(true);
        }

        if (this.pos.trainingMode) {
            await this._ensureTrainingLine();
            this.currentOrder.setIsTraining(true);
        }

        if (this.pos.advanceMode){
            this.currentOrder.setIsAdvance(true);
        }

        return await super.validateOrder(isForce);
    },

    /**
     * Map a payment method to its FRCS TaxCore PaymentType string.
     * Supported values: Cash, Card, MobileMoney, WireTransfer, Check, Other
     */
    _mapPaymentType(paymentLine) {
        const method = paymentLine.payment_method_id;
        const methodName = (method?.name || "").toLowerCase().trim();
        const journalType = method?.type || "";

        // Match by journal type first (most reliable)
        if (journalType === "cash") {
            return "Cash";
        }
        // Then match by name keywords (handles "POS Cash", "Cash", etc.)
        if (methodName.includes("cash")) {
            return "Cash";
        }
        if (methodName.includes("wire") || methodName.includes("wire transfer")) {
            return "WireTransfer";
        }
        if (methodName.includes("check") || methodName.includes("cheque")) {
            return "Check";
        }
        if (methodName.includes("mobile") || methodName.includes("mpesa") ||
            methodName.includes("vodafone") || methodName.includes("mpaisa")) {
            return "MobileMoney";
        }
        if (methodName.includes("card") || methodName.includes("visa") ||
            methodName.includes("master") || methodName.includes("eftpos")) {
            return "Card";
        }
        // Default to Card for any unrecognised electronic payment
        return "Card";
    },

    async _finalizeValidation() {
        const order = this.currentOrder;
        if (!order) {
            return super._finalizeValidation(...arguments);
        }

        const hasRefundLines = order.getHasRefundLines();
        const isRefund = hasRefundLines;

        const isAdvance = this.pos.advanceMode || order.isAdvance?.();
        const isProforma = this.pos.proformaMode || order.isProforma?.();
        const isTraining = this.pos.trainingMode || order.isTraining?.();

        const invoiceInput = document.getElementById("invoiceInput");
        const invoiceOutput = document.getElementById("invoiceOutput");
        const taxcoreButton = document.getElementById("taxcore_sign_element");
        if (!invoiceInput || !invoiceOutput || !taxcoreButton) {
            console.warn("TaxCore input/output elements missing");
            return super._finalizeValidation(...arguments);
        }

        const originalOrder =
        this.currentOrder
            .get_orderlines()
            .map((line) => line.refunded_orderline_id?.order_id)
            .find(Boolean);

        const refundId =
        originalOrder && typeof originalOrder.id === "number"
            ? originalOrder.id
            : null;

        const sdcInvoice = await this.pos.data.call(
            "pos.order.fiscal.record",
            "get_sdc_invoice",
            [refundId]
        );

        let refundInvoiceLabel = null;
        if (refundId) {
            refundInvoiceLabel = await this.pos.data.call(
                "pos.order.fiscal.record",
                "get_invoice_label",
                [refundId]
            );
        }

        // Fetch POS number in correct FRCS format: accreditation/version
        const posNumber = await this.pos.data.call(
            "frcs.vsdc.config",
            "get_pos_number",
            [this.pos.company.id]
        );

        const invoiceType = ["Normal", "Refund", "Copy", "Training", "Proforma", "Advance"];
        const transactionType = ["Sale", "Refund"];
        const resolveInvoiceType = (label) => {
            const normalized = (label || "").trim().toUpperCase();
            if (["AS", "AR", "ADVANCE SALE", "ADVANCE REFUND", "ADVANCE"].includes(normalized)) {
                return invoiceType[5];
            }
            if (["PS", "PR", "PROFORMA SALE", "PROFORMA REFUND", "PROFORMA"].includes(normalized)) {
                return invoiceType[4];
            }
            if (["TS", "TR", "TRAINING SALE", "TRAINING REFUND", "TRAINING"].includes(normalized)) {
                return invoiceType[3];
            }
            return invoiceType[0];
        };

        let transaction_type;
        let invoice_type;
        let sdc_invoice = "";

        if (isRefund){
            invoice_type = resolveInvoiceType(refundInvoiceLabel);
            transaction_type = transactionType[1];
            sdc_invoice = sdcInvoice;
        } else if (isAdvance){
            invoice_type = invoiceType[5];
            transaction_type = transactionType[0];
            sdc_invoice = "";
        } else if (isProforma){
            invoice_type = invoiceType[4];
            transaction_type = transactionType[0];
            sdc_invoice = "";
        } else if (isTraining){
            invoice_type = invoiceType[3];
            transaction_type = transactionType[0];
            sdc_invoice = "";
        } else {
            invoice_type = invoiceType[0];
            transaction_type = transactionType[0];
            sdc_invoice = "";
        }

        const items = await Promise.all(
            order.get_orderlines().map(async (line) => {
                const taxLabel = await this.pos.data.call(
                    "pos.order.fiscal.record",
                    "get_tax_label",
                    [line.get_product()?.id]
                );

                const labels = taxLabel ? [taxLabel] : DEFAULT_LABEL.slice();
                let quantity = line.get_quantity();
                const discount = line.get_discount();

                if (transaction_type === transactionType[1]) {
                    quantity = Math.abs(quantity);
                }

                // GTIN: use barcode field, required by FRCS
                const gtin = line.product?.barcode || line.product?.default_code || null;

                return {
                    GTIN: gtin,
                    Name: line.get_full_product_name() || "Item",
                    Quantity: quantity,
                    Discount: discount,
                    Labels: labels,
                    unitPrice: line.get_price_with_tax(),
                    TotalAmount: Math.abs(line.get_price_with_tax()),
                };
            })
        );

        // Build payment array with full FRCS-required payment types
        const paymentTypes = order.payment_ids.map((line) => {
            return {
                Amount: line.get_amount(),
                PaymentType: this._mapPaymentType(line),
            };
        });

        console.log("Payment types sent to TaxCore:", paymentTypes);

        let invoicePayload;

        try {
            invoicePayload = {
                DateAndTimeOfIssue: new Date().toISOString(),
                Cashier: this.pos.get_cashier().name,
                BD: null,
                BuyerCostCenterId: null,
                invoiceType: invoice_type,
                transactionType: transaction_type,
                payment: paymentTypes,
                InvoiceNumber: posNumber,   // FIXED: now "74/1.0.0" format
                ReferentDocumentNumber: sdc_invoice,
                ReferentDocumentDT: "",
                Options: {
                    OmitTextualRepresentation: 0,
                    OmitQRCodeGen: 0,
                },
                Items: items,
            };
        } catch (err) {
            console.error("Taxcore payload build failed: ", err);
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
            return; // abort finalize, do NOT call super
        }

        if (!taxcoreResponse || !taxcoreResponse.invoiceNumber) {
            console.error("TaxCore returned no SDC Invoice Number", taxcoreResponse);
            this.notification.add(_t("No SDC Invoice returned by TaxCore; order not saved."), { type: "danger" });
            return;
        }

        const invoice_label = taxcoreResponse.invoiceCounterExtension;
        const journal = taxcoreResponse;

        order.setTaxCoreResponse(taxcoreResponse);
        order.setInvoiceNumber(posNumber);
        order.setSDCInvoice(taxcoreResponse.invoiceNumber);
        order.setInvoiceLabel(invoice_label);

        const result = await super._finalizeValidation(...arguments);

        let backendId = typeof order.id === "number" ? order.id : undefined;
        if (!backendId) {
            await this.pos.data.syncData();
            backendId = typeof order.id === "number" ? order.id : undefined;
        }
        if (!backendId) {
            console.warn("No backend order id yet; skipping print job");
            return result;
        }

        if (journal) {
            await this.pos.data.execute({
                type: "write",
                model: "pos.order",
                ids: [backendId],
                values: { taxcore_journal: JSON.stringify(journal) },
            });

            await this.pos.data.call(
                "pos.order",
                "action_pos_order_paid",
                [backendId]
            );

            await this.pos.data.call(
                "pos.print.job",
                "cron_process_jobs",
                []
            );
        }

        order.setProcessingLock?.(false);
        return result;
    },
});



patch(PosOrder.prototype, {
    //Display TaxCore response on POS receipt
    export_for_printing() {
        const data = super.export_for_printing(...arguments);
        if (this.taxcore_response && this.taxcore_response.status_code !== 400 && this.taxcore_response.journal) {

            const journalLines = this.taxcore_response.journal.split('\r\n');
            const endLine = journalLines[journalLines.length - 2];
            const beforeEnd = journalLines.slice(0,-2).map((line,i)=>({
                text:line,
                idx:i
            }));

            data.taxcore_response = {
                ...this.taxcore_response,
                journal_before_end: beforeEnd,
                journal_end_line: endLine,
            };
        }
        return data;
    },

    setTaxCoreResponse(payload){
        this.taxcore_payload = payload;
        this.taxcore_response = payload;
    },

    setInvoiceNumber(invNum){
        this.invoice_number = invNum;
    },

    setSDCInvoice(SDCInv){
        this.sdc_invoice = SDCInv;
    },

    setInvoiceLabel(invLabel){
        this.invoice_label = invLabel;
    },

    setup(vals) {
        super.setup(vals);
        this.taxcore_payload = vals.taxcore_payload || null;
        this.invoice_number = vals.invoice_number || null;
        this.sdc_invoice = vals.sdc_invoice || null;
        this.invoice_label = vals.invoice_label || null;
    },

    serialize(){
        const data = super.serialize(...arguments);
        if(this.taxcore_payload){
            data.taxcore_payload = this.taxcore_payload;
        }
        if(this.invoice_number){
            data.invoice_number = this.invoice_number;
        }
        if(this.sdc_invoice){
            data.sdc_invoice = this.sdc_invoice;
        }
        if(this.invoice_label){
            data.invoice_label = this.invoice_label;
        }
        data.is_proforma = !!this.is_proforma;
        data.is_training = !!this.is_training;
        data.is_advance = !!this.is_advance;

        return data;
    },
});
