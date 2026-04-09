from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Compatibility flag used by some settings views (e.g., purchase_stock) to
    # decide whether to display Sales-related options. Define it here so the
    # view parsing never fails even if Sales is not installed.
    is_installed_sale = fields.Boolean(string="Sale Installed", compute='_compute_is_installed_sale')

    def _compute_is_installed_sale(self):
        Module = self.env['ir.module.module']
        installed = bool(Module.search([('name', 'in', ['sale', 'sale_management']), ('state', '=', 'installed')], limit=1))
        for rec in self:
            rec.is_installed_sale = installed

