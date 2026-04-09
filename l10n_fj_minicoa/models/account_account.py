from odoo import models, fields


class AccountAccount(models.Model):
    _inherit = 'account.account'

    # Ensure company is explicitly present on accounts (some customizations/imports
    # may have dropped/cleared it). In standard Odoo this field exists and is required;
    # this override keeps it required and provides a sane default for new records.
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

