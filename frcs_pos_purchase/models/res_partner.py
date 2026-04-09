from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    frcs_tin = fields.Char(
        string=_("FRCS TIN"),
        help=_("Tax Identification Number as registered with FRCS."),
    )
    frcs_is_vat_registered = fields.Boolean(
        string=_("VAT Registered"),
        help=_("Identify whether the partner is registered for VAT with FRCS."),
    )
