from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Mirror the template's computed Total Price for POS use
    # Not stored: avoids DB column requirement and works across DBs without upgrade hiccups
    x_total_price = fields.Monetary(
        string='Total Price (FJ$)',
        compute='_compute_x_total_price',
        currency_field='currency_id',
        store=False,
    )

    frcs_tax_label = fields.Selection(
        related="product_tmpl_id.frcs_tax_label",
        readonly=False, 
        store=True,
    )

    @api.depends('product_tmpl_id.x_total_price')
    def _compute_x_total_price(self):
        """Safely mirror total price for POS without triggering recursive writes.
        Adds a skip flag in context during recompute and guards against transient
        compute failures so we don't bubble up transaction errors.
        """
        for product in self.with_context(skip_tax_sync=True):
            try:
                value = product.product_tmpl_id.x_total_price
                product.x_total_price = value if value is not None else 0.0
            except Exception:
                product.x_total_price = 0.0

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        # Ensure our field is available in the POS payload
        if 'x_total_price' not in fields_list:
            fields_list.append('x_total_price')
        # Only include x_price_incl_tax if it exists on product.product in this DB
        if 'x_price_incl_tax' in self._fields and 'x_price_incl_tax' not in fields_list:
            fields_list.append('x_price_incl_tax')
        if 'total_price' not in fields_list:
            fields_list.append('total_price')
        return fields_list

    # POS expects 'total_price' as a simple float; bridge template field
    total_price = fields.Float(
        string='Total Price (Tax Included)',
        related='product_tmpl_id.total_price',
        store=False,
        readonly=True,
    )
