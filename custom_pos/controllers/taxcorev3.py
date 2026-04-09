from odoo import http
from odoo.http import request

class TaxCoreV3(http.Controller):

    @http.route("/taxcore/sign_v3", type="json", auth="user", csrf=False)
    def sign_v3(self, invoice):
        return request.env["taxcore.client"].send_invoice_v3(invoice)
