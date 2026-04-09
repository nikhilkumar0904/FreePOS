/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class FrcsInventoryDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            top_products: [],
            expiring_products: [],
        });

        onWillStart(async () => {
            try {
                this.state.top_products = await this.orm.call(
                    "product.template",
                    "get_top_selling_products",
                    [],
                    {}
                );
            } catch (e) {
                // Keep dashboard usable even if source tables don't exist
                this.state.top_products = [];
            }
            try {
                this.state.expiring_products = await this.orm.call(
                    "product.template",
                    "get_expiring_products",
                    [],
                    {}
                );
            } catch (e) {
                this.state.expiring_products = [];
            }
        });
    }

    getTopProducts() {
        return this.state.top_products;
    }

    getExpiringProducts() {
        return this.state.expiring_products;
    }
}

FrcsInventoryDashboard.template = "frcs_inventory.InventoryDashboard";
registry.category("actions").add("frcs_inventory_dashboard", FrcsInventoryDashboard);

export default FrcsInventoryDashboard;

