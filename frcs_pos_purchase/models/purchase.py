from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    frcs_vendor_tin = fields.Char(
        string=_("Vendor TIN"),
        related="partner_id.frcs_tin",
        store=True,
    )
    frcs_vendor_vat_registered = fields.Boolean(
        string=_("Vendor VAT Registered"),
        related="partner_id.frcs_is_vat_registered",
        store=True,
    )
    frcs_qty_ordered = fields.Float(
        string=_("Ordered Qty (FRCS)"),
        compute="_compute_frcs_receive_summary",
        digits="Product Unit of Measure",
    )
    frcs_qty_received = fields.Float(
        string=_("Received Qty (FRCS)"),
        compute="_compute_frcs_receive_summary",
        digits="Product Unit of Measure",
    )
    frcs_qty_to_receive = fields.Float(
        string=_("To Receive Qty (FRCS)"),
        compute="_compute_frcs_receive_summary",
        digits="Product Unit of Measure",
    )
    frcs_receive_status = fields.Selection(
        [
            ("none", _("Not received")),
            ("partial", _("Partially received")),
            ("full", _("Fully received")),
        ],
        string=_("Receive Status (FRCS)"),
        compute="_compute_frcs_receive_summary",
    )

    def button_confirm(self):
        self.ensure_one()
        require_tin = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("frcs_pos_purchase.require_vendor_tin", default="False")
        )
        if (
            require_tin
            and require_tin.strip().lower() in ("true", "1", "yes")
            and self.frcs_vendor_vat_registered
            and not (self.frcs_vendor_tin or "").strip()
        ):
            raise ValidationError(_("Vendor TIN is required by configuration."))
        return super().button_confirm()

    def _compute_frcs_receive_summary(self):
        tolerance = 1e-6
        for order in self:
            ordered_total = 0.0
            received_total = 0.0
            for line in order.order_line:
                if line.product_id and line.product_id.type == "product":
                    ordered_total += line.product_qty or 0.0
                    received_total += line.qty_received or 0.0
            ordered_total = max(ordered_total, 0.0)
            received_total = max(received_total, 0.0)
            qty_to_receive = ordered_total - received_total
            if qty_to_receive < 0:
                qty_to_receive = 0.0

            status = "none"
            if ordered_total > tolerance:
                if received_total <= tolerance:
                    status = "none"
                elif received_total >= ordered_total - tolerance:
                    status = "full"
                else:
                    status = "partial"

            order.frcs_qty_ordered = ordered_total
            order.frcs_qty_received = received_total
            order.frcs_qty_to_receive = qty_to_receive
            order.frcs_receive_status = status


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    frcs_vat_label = fields.Selection(
        selection="_get_frcs_vat_label_selection",
        string=_("FRCS VAT Label"),
        help=_("FRCS VAT label selected for reporting consistency."),
    )

    @api.model
    def _get_frcs_vat_label_selection(self):
        labels = self.env["frcs.purchase.tax.label"].search(
            [("active", "=", True)], order="code"
        )
        return [(label.code, label.name) for label in labels]
