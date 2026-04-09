from odoo import _, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    frcs_vendor_tin = fields.Char(
        string=_("Vendor TIN"),
        related="partner_id.frcs_tin",
        store=False,
        readonly=True,
    )
