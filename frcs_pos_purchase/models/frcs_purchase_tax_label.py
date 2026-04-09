from odoo import _, fields, models


class FrcsPurchaseTaxLabel(models.Model):
    _name = "frcs.purchase.tax.label"
    _description = "FRCS Purchase VAT Label"
    _order = "code"

    code = fields.Selection(
        selection=[("VAT12_5", "VAT12_5"), ("VAT0", "VAT0")],
        string=_("Code"),
        required=True,
        index=True,
    )
    name = fields.Char(
        string=_("Label"),
        required=True,
    )
    rate = fields.Float(
        string=_("Rate (%)"),
        digits=(3, 2),
        required=True,
    )
    active = fields.Boolean(
        default=True,
    )

    _sql_constraints = [
        ("frcs_purchase_tax_label_code_unique", "unique(code)", _("The code must be unique.")),
    ]
