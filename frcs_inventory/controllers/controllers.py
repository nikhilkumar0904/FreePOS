# -*- coding: utf-8 -*-
# from odoo import http


# class FrcsInventory(http.Controller):
#     @http.route('/frcs_inventory/frcs_inventory', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/frcs_inventory/frcs_inventory/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('frcs_inventory.listing', {
#             'root': '/frcs_inventory/frcs_inventory',
#             'objects': http.request.env['frcs_inventory.frcs_inventory'].search([]),
#         })

#     @http.route('/frcs_inventory/frcs_inventory/objects/<model("frcs_inventory.frcs_inventory"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('frcs_inventory.object', {
#             'object': obj
#         })

