from odoo import http
from odoo.http import request
import io
import xlsxwriter
from datetime import datetime

class FrcsInventoryXlsxController(http.Controller):

    @http.route('/frcs_inventory/product_master_xlsx', type='http', auth='user')
    def frcs_product_master_xlsx(self, **kwargs):
        # Fetch products; you can add filters via kwargs if needed later
        products = request.env['product.template'].sudo().search([])

        # Create workbook in memory
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('Product Master')

        # Formats
        bold = workbook.add_format({'bold': True})
        datefmt = workbook.add_format({'num_format': 'yyyy-mm-dd hh:mm'})

        # Headers
        headers = ['Internal Ref', 'Name', 'Barcode', 'GTIN', 'FRCS Label', 'Last Modified By', 'Last Modified At']
        for col, h in enumerate(headers):
            ws.write(0, col, h, bold)

        # Rows
        row = 1
        for p in products:
            ws.write(row, 0, p.default_code or '')
            ws.write(row, 1, p.display_name or '')
            ws.write(row, 2, p.barcode or '')
            ws.write(row, 3, p.frcs_gtin or '')
            ws.write(row, 4, p.frcs_tax_label or '')
            ws.write(row, 5, p.write_uid.display_name if p.write_uid else '')
            # write_date is a string/utc timestamp; let’s try to render nicely
            if p.write_date:
                # Odoo stores UTC; we’ll just dump it as text or parse if needed
                ws.write(row, 6, str(p.write_date))
            else:
                ws.write(row, 6, '')
            row += 1

        workbook.close()
        output.seek(0)

        filename = f"FRCS_Product_Master_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', f'attachment; filename="{filename}"'),
        ]
        return request.make_response(output.read(), headers=headers)
