print("? frcs_inventory.models.pos_session successfully loaded (tax-inclusive loader active, legacy loader fallback)")

import logging
from odoo import models

_logger = logging.getLogger(__name__)


class PosSession(models.Model):
    _inherit = 'pos.session'

    def _pos_ui_models_to_load(self):
        res = super()._pos_ui_models_to_load()
        if 'product.product' not in res:
            res.append('product.product')
        _logger.info("frcs_inventory: models to load -> %s", res)
        return res

    # _get_pos_ui_product_product removed - standard POS loader handles product fields
    # Fields are exposed via _load_pos_data_fields in product_product.py