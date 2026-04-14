from odoo import models


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        """Ensure res.partner is loaded so FRCS B2B fields are available in POS."""
        res = super()._pos_ui_models_to_load()
        if 'res.partner' not in res:
            res.append('res.partner')
        return res
