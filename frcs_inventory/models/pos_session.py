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

    def _get_pos_ui_product_product(self, params):
        """Legacy loader version for product fields.
        Loads only the fields we need and that actually exist.
        """
        Product = self.env['product.product'].sudo()

        fields_to_load = [
            'display_name', 'name', 'list_price', 'taxes_id',
            'x_total_price', 'x_price_incl_tax', 'product_tmpl_id.frcs_tax_label',
        ]
        # Keep only existing fields on this DB
        fields_to_load = [f for f in fields_to_load if f in Product._fields]

        domain = (
            params.get('domain')
            or params.get('search_params', {}).get('domain')
            or []
        )

        _logger.info(
            "frcs_inventory: loading product.product fields -> %s with domain %s",
            fields_to_load,
            domain,
        )
        return Product.search_read(domain, fields_to_load)