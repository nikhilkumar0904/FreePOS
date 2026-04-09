from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    frcs_require_vendor_tin = fields.Boolean(
        string="Require Vendor TIN on Purchase Orders",
        config_parameter="frcs_pos_purchase.require_vendor_tin",
        help="When enabled, purchase orders cannot be confirmed unless the vendor has an FRCS TIN.",
    )
