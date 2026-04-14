from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _load_pos_data_fields(self, config_id):
        """Ensure FRCS B2B fields are included in the POS partner data payload."""
        fields_list = super()._load_pos_data_fields(config_id)
        for f in ['vat', 'frcs_tin', 'frcs_is_vat_registered', 'frcs_cost_center']:
            if f not in fields_list:
                fields_list.append(f)
        return fields_list
