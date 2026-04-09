# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class frcs_inventory(models.Model):
#     _name = 'frcs_inventory.frcs_inventory'
#     _description = 'frcs_inventory.frcs_inventory'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

# -*- coding: utf-8 -*-
from odoo import models, fields, api

#class ProductTemplate(models.Model):
 #   _inherit = 'product.template'

  #  x_frcs_tax = fields.Many2one(
   #     'account.tax',
   #     string="FRCS Tax",
   #     domain="[('type_tax_use', '=', 'sale')]",
     #   help="Select the applicable FRCS VAT for this product."
  #  )
