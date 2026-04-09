from odoo import models, fields, api
import logging
import json

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_label = fields.Char(string="Invoice Label")
    taxcore_journal = fields.Text(string="TaxCore Jounal")
    is_proforma = fields.Boolean(default=False)
    is_training = fields.Boolean(default=False)
    is_advance = fields.Boolean(default=False)


    def _enqueue_taxcore_print(self):
        for order in self:
            ip = order.config_id.raw_printer_ip
            if not ip:
                continue
            # Pick what you want to print (example uses TaxCore Journal)
            journal = None
            try:
                # If you store JSON in a field; adapt to your field name
                journal = (order.taxcore_journal or {}).get('Journal')
            except Exception:
                journal = None
            if not journal:
                continue
            self.env['pos.print.job'].create({
                'order_id': order.id,
                'payload': journal,
                'printer_ip': ip,
            })

    @api.model
    def _process_order(self, order, existing_order):
        if order.get("is_proforma") or order.get("is_training"):
            order = dict(order)
            order["payment_ids"] =[]
            order["amount_paid"] = 0.0
            order["amount_return"]=0.0

        res = super()._process_order(order, existing_order)

        return res

    def _create_order_picking(self):
        normal = self.filtered(lambda o: not o.is_proforma and not o.is_training and not o.is_advance)
        if normal:
            return super(PosOrder, normal)._create_order_picking()
        return True

    def _create_account_move(self):
        normal = self.filtered(lambda o: not o.is_proforma and not o.is_training  and not o.is_advance)
        if normal:
            return super(PosOrder, normal)._create_account_move()
        return False




    #PRINTERRRR
    def action_pos_order_paid(self):
        _logger.info("action_pos_order_paid() triggered from frontend")

        overall_result = True
        for order in self:
            _logger.info("Processing order ID: %s", order.id)
            _logger.info("Printer IP: %s", order.config_id.raw_printer_ip)
            payload = None
            if order.taxcore_journal:
                try:
                    # If already a dict, skip parsing
                    if isinstance(order.taxcore_journal, dict):
                        payload = order.taxcore_journal
                    else:
                        payload = json.loads(order.taxcore_journal.replace("'", '"'))
                except Exception as e:
                    _logger.warning("Failed to parse taxcore_journal: %s", e)
            _logger.info("Has journal: %s", bool(payload)) 

            if order.is_proforma or order.is_training:
                # Those modes intentionally skip payments, so mark them paid manually
                _logger.info("Skipping paid check for special order %s", order.id)
                order.write({'state': 'paid'})
                res = True
            else:
                res = super(PosOrder, order).action_pos_order_paid()
            overall_result = overall_result and bool(res)

            ip = order.config_id.raw_printer_ip
            if not (ip and payload):
                _logger.warning("Skipping print job: IP or journal missing for %s", order.id)
                continue

            journal_text = payload.get("Journal", "") if payload else ""
            lines = [line for line in journal_text.split("\r\n") if line.strip()]
            end_line = lines.pop(-1) if lines else ""
            

            print_payload = {
                "lines": lines,
                "end_line": end_line,
                "verification_qr":payload.get("VerificationQRCode") if payload else None,
            }


            if ip and payload:
                _logger.info("Creating print job for order %s", order.id)
                self.env['pos.print.job'].sudo().create({
                    'order_id': order.id,
                    'printer_ip': ip,
                    'payload': json.dumps(print_payload),
                })

            else:
                _logger.warning(" Skipping print job: IP or journal missing for %s", order.id)

        return overall_result
