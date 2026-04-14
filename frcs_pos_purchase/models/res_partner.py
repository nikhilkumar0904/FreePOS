from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    frcs_tin = fields.Char(
        string=_("FRCS TIN"),
        help=_("Tax Identification Number as registered with FRCS. Used as Buyer TIN on B2B fiscal receipts."),
    )
    frcs_is_vat_registered = fields.Boolean(
        string=_("VAT Registered"),
        help=_("Identify whether the partner is registered for VAT with FRCS."),
    )
    frcs_cost_center = fields.Char(
        string=_("Cost Centre"),
        help=_("Buyer Cost Centre for B2B fiscal invoices. Set once per business customer; "
               "automatically included on TaxCore fiscal receipts when present."),
    )

    def _load_pos_data_fields(self, config_id):
        """Expose FRCS B2B fields to the POS frontend."""
        fields_list = super()._load_pos_data_fields(config_id)
        for f in ['frcs_tin', 'frcs_is_vat_registered', 'frcs_cost_center']:
            if f not in fields_list:
                fields_list.append(f)
        return fields_list
