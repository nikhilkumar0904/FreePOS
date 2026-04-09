/**
 * Odoo OWL (v17+) patch: force orderline display price to be tax-included.
 */
import { patch } from '@web/core/utils/patch';
import { PosOrderline } from '@point_of_sale/app/models/pos_order_line';
import { ProductCard } from '@point_of_sale/app/generic_components/product_card/product_card';

patch(PosOrderline.prototype, 'frcs_inventory.pos_total_price', {
    get_display_price() {
        // Always display tax-included price on the line
        return this.get_price_with_tax();
    },
});

// Show tax-included price on product cards if a backend total is provided
patch(ProductCard.prototype, 'frcs_inventory.product_card_total_price', {
    /**
     * Extend the template context with a formatted price if available.
     * The template does not render price by default, but other modules/components
     * that read ProductCard props can use this helper.
     */
    get totalPriceStr() {
        const p = this.props.product || {};
        const total = p.total_price ?? p.x_total_price ?? p.list_price;
        return this.env.utils.formatCurrency(total);
    },
});
