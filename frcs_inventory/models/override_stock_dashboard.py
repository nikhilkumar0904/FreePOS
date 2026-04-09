from odoo import models, http
from odoo.http import request


class StockDashboardHide(models.Model):
    _inherit = 'ir.actions.client'

    def read(self, fields=None):
        """Hide/neutralize the default stock dashboard client action.
        When the web client tries to render tag='stock_dashboard',
        rewrite it to a disabled tag so the dashboard does not render.
        """
        res = super().read(fields)
        for r in res:
            try:
                if r.get('tag') == 'stock_dashboard':
                    r['tag'] = 'disabled'
                    r['help'] = 'Inventory Overview has been replaced by FRCS Inventory Dashboard.'
            except Exception:
                # Never block reads for other client actions
                continue
        return res


class InventoryRedirect(http.Controller):
    @http.route(['/odoo/inventory', '/inventory'], type='http', auth='user')
    def redirect_inventory(self, **kwargs):
        """Redirect legacy Inventory Overview URLs to the FRCS dashboard."""
        return request.redirect('/web#action=frcs_inventory.action_frcs_inventory_dashboard')

