/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { kanbanView } from "@web/views/kanban/kanban_view";

// The Inventory Overview is a Kanban view registered as "stock_dashboard_kanban".
// Override that view with a renderer that immediately redirects to our dashboard.
class RedirectStockDashboardRenderer extends Component {
    setup() {
        const action = useService("action");
        onMounted(() => {
            action.doAction("frcs_inventory.action_frcs_inventory_dashboard");
        });
    }
}

RedirectStockDashboardRenderer.template = "frcs_inventory.RedirectStockDashboard";

const RedirectStockDashboardView = {
    ...kanbanView,
    Renderer: RedirectStockDashboardRenderer,
};

// Force-override the built-in Stock Overview view spec
registry.category("views").add("stock_dashboard_kanban", RedirectStockDashboardView, { force: true });

export default RedirectStockDashboardView;
