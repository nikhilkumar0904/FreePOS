/** @odoo-module **/
/**
 * FRCS V-SDC Session Authentication
 * ----------------------------------
 * On POS operation start, performs a mutual TLS authentication handshake
 * with the TaxCore V-SDC by calling the tax-rates endpoint using the
 * configured client certificate.
 *
 * This satisfies the FRCS certification requirement:
 *   "Upon operation start, the POS and V-SDC are mutually authenticated"
 *
 * If authentication succeeds: POS opens normally, status shown in navbar.
 * If authentication fails: cashier is warned but can still proceed
 *   (to avoid blocking the POS if V-SDC is temporarily unavailable).
 */
import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/navbar/navbar";
import { _t } from "@web/core/l10n/translation";
import { useState } from "@odoo/owl";

patch(Navbar.prototype, {
    setup() {
        super.setup(...arguments);
        // Reactive state for V-SDC auth status shown in the navbar
        this.vsdcState = useState({
            status: "checking",  // "checking" | "ok" | "error"
            message: "",
        });
        // Run authentication in the background on startup
        this._authenticateVSDC();
    },

    async _authenticateVSDC() {
        try {
            const result = await this.pos.data.call(
                "taxcore.client",
                "authenticate_vsdc",
                []
            );

            if (result && result.success) {
                this.vsdcState.status = "ok";
                this.vsdcState.message = _t("V-SDC Connected");
                console.log("[FRCS] V-SDC mutual authentication successful on session start.");
            } else {
                this.vsdcState.status = "error";
                this.vsdcState.message = _t("V-SDC Unreachable");
                console.warn("[FRCS] V-SDC authentication failed on session start:", result?.error);
                this._showVSDCWarning(result?.error || "Unknown error");
            }
        } catch (err) {
            this.vsdcState.status = "error";
            this.vsdcState.message = _t("V-SDC Unreachable");
            console.error("[FRCS] V-SDC authentication error on session start:", err);
            this._showVSDCWarning(err.message || String(err));
        }
    },

    _showVSDCWarning(errorDetail) {
        // Non-blocking warning — cashier is informed but can still operate
        this.notification.add(
            _t(
                "Warning: Could not authenticate with TaxCore V-SDC on session start. " +
                "Fiscal invoices will fail until the connection is restored. " +
                "Error: %s",
                errorDetail
            ),
            { type: "warning", sticky: true }
        );
    },
});
