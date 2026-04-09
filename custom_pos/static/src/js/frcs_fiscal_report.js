/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class FiscalReportClientAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            filters: {
                start: "",
                end: "",
                configs: [],
                sessions: [],
            },
            options: {
                configs: [],
                sessions: [],
            },
            loading: false,
            report: null,
            pagination: {
                page: 1,
                pageSize: 10,
            },
        });
        this.loadFilterOptions();
    }

    async loadFilterOptions() {
        this.state.options.configs = await this.orm.searchRead(
            "pos.config",
            [],
            ["name"]
        );
        this.state.options.sessions = await this.orm.searchRead(
            "pos.session",
            [],
            ["name", "config_id"]
        );
    }

    onDateChange(field, ev) {
        this.state.filters[field] = ev.target.value;
    }

    onSelectionChange(field, ev) {
        const values = Array.from(ev.target.selectedOptions).map((opt) =>
            Number(opt.value)
        );
        this.state.filters[field] = values;
    }

    clearSelection(field) {
        if (!Object.prototype.hasOwnProperty.call(this.state.filters, field)) {
            return;
        }
        this.state.filters[field] = [];
    }

    async generateReport(ev) {
        ev.preventDefault();
        const { start, end, configs, sessions } = this.state.filters;
        if (!start || !end) {
            this.notification.add(
                _t("Please select both start and end dates."),
                { type: "warning" }
            );
            return;
        }
        const startDate = new Date(start);
        const endDate = new Date(end);
        if (isNaN(startDate) || isNaN(endDate)) {
            this.notification.add(
                _t("Invalid date(s) selected."),
                { type: "warning" }
            );
            return;
        }
        if (startDate > endDate) {
            this.notification.add(
                _t("Start date must be before or equal to end date."),
                { type: "warning" }
            );
            return;
        }
        const startISO = this.toBoundaryIso(start, "start");
        const endISO = this.toBoundaryIso(end, "end");
        this.state.loading = true;
        try {
            const report = await this.orm.call("pos.order.fiscal.record", "get_report_data", [], {
                start_dt: startISO,
                end_dt: endISO,
                config_ids: configs,
                session_ids: sessions,
            });
            const defaultCounts = {
                normal_sale: 0,
                normal_refund: 0,
                advance_sale: 0,
                advance_refund: 0,
            };
            const defaultTotals = {
                sale: 0,
                refund: 0,
                per_type: { ...defaultCounts },
            };
            report.sold_items = report.sold_items || [];
            report.payment_totals = report.payment_totals || {};
            report.invoice_counts = { ...defaultCounts, ...(report.invoice_counts || {}) };
            report.invoice_totals = {
                ...defaultTotals,
                ...(report.invoice_totals || {}),
            };
            report.invoice_totals.per_type = {
                ...defaultTotals.per_type,
                ...(report.invoice_totals.per_type || {}),
            };
            report.invoiceSummary = this.prepareInvoiceSummary(report);
            report.overviewCards = this.prepareOverview(report);
            this.state.pagination.page = 1;
            this.state.report = report;
        } catch (error) {
            this.notification.add(
                error?.message || _t("Unable to generate fiscal report."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    get hasReport() {
        return Boolean(this.state.report);
    }

    formatAmount(amount) {
        return (amount || 0).toFixed(2);
    }

    formatRate(rate) {
        return `${((rate || 0)).toFixed(2)}%`;
    }

    get paginatedSoldItems() {
        if (!this.state.report) {
            return [];
        }
        const items = this.state.report.sold_items || [];
        const start = (this.state.pagination.page - 1) * this.state.pagination.pageSize;
        const end = start + this.state.pagination.pageSize;
        return items.slice(start, end);
    }

    get soldItemsTotalPages() {
        if (!this.state.report) {
            return 1;
        }
        const items = this.state.report.sold_items || [];
        return Math.max(1, Math.ceil(items.length / this.state.pagination.pageSize));
    }

    nextSoldItemsPage() {
        if (this.state.pagination.page < this.soldItemsTotalPages) {
            this.state.pagination.page += 1;
        }
    }

    prevSoldItemsPage() {
        if (this.state.pagination.page > 1) {
            this.state.pagination.page -= 1;
        }
    }

    get paymentEntries() {
        if (!this.state.report || !this.state.report.payment_totals) {
            return [];
        }
        const keys = ["cash", "card", "mobile_money"];
        return keys.map((key) => [key, this.state.report.payment_totals[key] || 0]);
    }

    labelize(label) {
        return (label || "")
            .split("_")
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(" ");
    }

    formatDateOnly(value) {
        if (!value) {
            return "";
        }
        const date = new Date(value);
        if (isNaN(date.getTime())) {
            return (value || "").split("T")[0];
        }
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    toBoundaryIso(dateString, boundary) {
        if (!dateString) {
            return null;
        }
        const normalized = dateString.trim();
        if (!/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
            return null;
        }
        const suffix = boundary === "end" ? "23:59:59" : "00:00:00";
        const date = new Date(`${normalized}T${suffix}`);
        if (isNaN(date.getTime())) {
            return null;
        }
        return date.toISOString().slice(0, 19).replace("T", " ");
    }

    prepareInvoiceSummary(report) {
        const map = [
            { key: "normal_sale", label: _t("Normal Sale") },
            { key: "normal_refund", label: _t("Normal Refund") },
            { key: "advance_sale", label: _t("Advance Sale") },
            { key: "advance_refund", label: _t("Advance Refund") },
        ];
        return map.map((item) => ({
            label: item.label,
            count: report.invoice_counts[item.key] || 0,
            total: report.invoice_totals.per_type[item.key] || 0,
        }));
    }

    prepareOverview(report) {
        const totalInvoices = Object.values(report.invoice_counts || {}).reduce(
            (sum, value) => sum + (value || 0),
            0
        );
        return [
            {
                label: _t("Total Sales"),
                value: this.formatAmount(report.invoice_totals.sale),
                suffix: "",
                description: _t("Normal + Advance sales"),
                bg: "linear-gradient(135deg, #4c6ef5 0%, #7950f2 100%)",
                color: "#fff",
            },
            {
                label: _t("Total Refunds"),
                value: this.formatAmount(report.invoice_totals.refund),
                suffix: "",
                description: _t("Normal + Advance refunds"),
                bg: "linear-gradient(135deg, #f76707 0%, #f7a832 100%)",
                color: "#fff",
            },
            {
                label: _t("Invoices"),
                value: totalInvoices,
                suffix: "",
                description: _t("Processed in selected period"),
                bg: "linear-gradient(135deg, #12b886 0%, #40c057 100%)",
                color: "#fff",
            },
        ];
    }
}

FiscalReportClientAction.template = "custom_pos.FiscalReportClientAction";

registry.category("actions").add(
    "custom_pos_fiscal_report",
    FiscalReportClientAction
);
