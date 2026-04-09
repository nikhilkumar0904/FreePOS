from odoo import fields, models

class PosConfig(models.Model):
    _inherit = 'pos.config'

    raw_printer_ip= fields.Char(
        string="ESC/POS Printer IP",
        help="IP of the ESC/POS receipt printer (TCP 9100).",
    )
    