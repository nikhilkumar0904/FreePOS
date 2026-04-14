from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        """Ensure res.partner is in the POS loaded models
        so FRCS B2B fields (frcs_tin, frcs_cost_center) are available in JS."""
        res = super()._pos_ui_models_to_load()
        if 'res.partner' not in res:
            res.append('res.partner')
        return res
