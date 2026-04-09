from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    frcs_label = fields.Char(
        string="FRCS Label",
        help="FRCS VAT label for TaxCore mapping (e.g., A, B, D, G).",
        size=2,
    )

