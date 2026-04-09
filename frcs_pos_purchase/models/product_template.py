from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    frcs_default_vat_label = fields.Selection(
        selection="_get_frcs_vat_label_selection",
        string=_("Default FRCS VAT Label"),
        help=_("Default VAT label for purchasing (info only)."),
    )

    @api.model
    def _get_frcs_vat_label_selection(self):
        labels = self.env["frcs.purchase.tax.label"].search(
            [("active", "=", True)], order="code"
        )
        return [(label.code, label.name) for label in labels]
