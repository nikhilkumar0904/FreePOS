from odoo import fields, models, api
from odoo.exceptions import UserError
import json

class PosOrderFiscalRecord(models.Model):
    _name = "pos.order.fiscal.record"
    _description = "TaxCore Payload"

    order_id = fields.Many2one(
        "pos.order",
        required=True,
        ondelete="cascade",
        index=True,
    )

    payload = fields.Json(string="TaxCore Payload")
    invoice_number = fields.Text(string="Invoice Number")
    received_at = fields.Datetime(
        default=fields.Datetime.now,
        readonly=True,
    )
    sdc_invoice = fields.Text(string="SDC Invoice Number", required=True)
    invoice_label = fields.Text(string="Invoice Label")

    @api.model 
    def get_invoice_number(self, order_id):
        record = self.search([("order_id", "=", order_id)], limit=1)
        return record.invoice_number if record else False
    
    @api.model 
    def get_created_time(self, order_id):
        record = self.search([("order_id", "=", order_id)], limit=1)
        return record.received_at if record else False
    
    @api.model
    def get_sdc_invoice(self, order_id):
        record = self.search([("order_id", "=", order_id)], limit=1)
        return record.sdc_invoice if record else False

    
    
    @api.model
    def get_invoice_label(self, order_id):
        record = self.search([("order_id", "=", order_id)], limit=1)
        return record.invoice_label if record else False
    
    @api.model
    def get_report_data(self, start_dt, end_dt, config_ids=None, session_ids=None):
        """Return the fiscal report payload for the provided filters."""
        start_dt, end_dt = self._prepare_period_bounds(start_dt, end_dt)
        record_domain = self._build_record_domain(start_dt, end_dt, config_ids, session_ids)
        fiscal_records = self.search(record_domain)
        orders = fiscal_records.mapped("order_id")
        lines = self.env["pos.order.line"].search([("order_id", "in", orders.ids)]) if orders else self.env["pos.order.line"]
        payments = self.env["pos.payment"].search([("pos_order_id", "in", orders.ids)]) if orders else self.env["pos.payment"]

        invoice_counts = self._get_invoice_counts(fiscal_records)
        invoice_totals = self._get_invoice_totals(fiscal_records)
        sold_items = self._get_sold_items(lines)
        payment_totals = self._get_payment_totals(payments)

        return {
            "period": self._prepare_period_summary(start_dt, end_dt),
            "invoice_counts": invoice_counts,
            "sold_items": sold_items,
            "invoice_totals": invoice_totals,
            "payment_totals": payment_totals,
        }
    
    def _build_record_domain(self, start_dt, end_dt, config_ids=None, session_ids=None):
        domain = [
            ("received_at", ">=", start_dt),
            ("received_at", "<=", end_dt),
            ("order_id.is_proforma", "=", False),
            ("order_id.is_training", "=", False),
        ]
        if config_ids:
            domain.append(("order_id.config_id", "in", config_ids))
        if session_ids:
            domain.append(("order_id.session_id", "in", session_ids))
        return domain
    
    def _prepare_period_bounds(self, start_dt, end_dt):
        if not start_dt or not end_dt:
            raise UserError("Fiscal reports require both a start and end datetime.")
        start_dt = fields.Datetime.to_datetime(start_dt)
        end_dt = fields.Datetime.to_datetime(end_dt)
        if end_dt < start_dt:
            raise UserError("The report end datetime must be greater than the start datetime.")
        return start_dt, end_dt
    
    def _prepare_period_summary(self, start_dt, end_dt):
        user = self.env.user
        start_local = fields.Datetime.context_timestamp(user, start_dt) if start_dt else False
        end_local = fields.Datetime.context_timestamp(user, end_dt) if end_dt else False
        return {
            "start_utc": start_dt,
            "end_utc": end_dt,
            "start": start_local.isoformat() if start_local else False,
            "end": end_local.isoformat() if end_local else False,
        }
    
    def _get_invoice_counts(self, fiscal_records):
        categories = {
            "normal_sale": 0,
            "normal_refund": 0,
            "advance_sale": 0,
            "advance_refund": 0,
        }
        for record in fiscal_records:
            key = self._classify_invoice_type(record)
            categories[key] += 1
        return categories

    def _get_invoice_totals(self, fiscal_records):
        totals = {
            "sale": 0.0,
            "refund": 0.0,
            "per_type": {
                "normal_sale": 0.0,
                "normal_refund": 0.0,
                "advance_sale": 0.0,
                "advance_refund": 0.0,
            },
        }
        for record in fiscal_records:
            classification = self._classify_invoice_type(record)
            amount = record.order_id.amount_total
            if classification in totals["per_type"]:
                totals["per_type"][classification] += amount
            if classification.endswith("sale"):
                totals["sale"] += amount
            else:
                totals["refund"] += abs(amount)
        return totals
    
    def _get_sold_items(self, order_lines):
        items = []
        user = self.env.user
        for line in order_lines:
            taxes = line.tax_ids_after_fiscal_position or line.product_id.taxes_id
            tax_rate = sum(t.amount for t in taxes) if taxes else 0.0
            tax_amount = line.price_subtotal_incl - line.price_subtotal
            order_dt = line.order_id.date_order if line.order_id else False
            order_local = (
                fields.Datetime.context_timestamp(user, order_dt)
                if order_dt
                else False
            )
            order_date = order_local.strftime("%Y-%m-%d") if order_local else False
            order_time = order_local.strftime("%H:%M:%S") if order_local else False
            items.append({
                "order_id": line.order_id.id,
                "order_name": line.order_id.name,
                "product_id": line.product_id.id,
                "product_name": line.full_product_name or line.product_id.display_name,
                "order_date": order_date,
                "order_time": order_time,
                "qty": line.qty,
                "price_unit": line.price_unit,
                "tax_rate": tax_rate,
                "tax_amount": tax_amount,
                "total": line.price_subtotal_incl,
            })
        return items
    
    def _get_payment_totals(self, payments):
        categories = [
            "cash",
            "card",
            "mobile_money",
        ]
        totals = {category: 0.0 for category in categories}
        for payment in payments:
            category = self._map_payment_category(payment.payment_method_id)
            totals[category] += payment.amount
        return totals
    
    def _map_payment_category(self, method):
        if not method:
            return "cash"
        name = (method.name or "").lower()
        journal = method.journal_id
        if method.type == "cash" or (journal and journal.type == "cash"):
            return "cash"
        if "card" in name or "visa" in name or "master" in name:
            return "card"
        if "mobile" in name or "mpesa" in name:
            return "mobile_money"
        return "cash"
    
    def _classify_invoice_type(self, fiscal_record):
        label = (fiscal_record.invoice_label or "").strip().upper()
        order = fiscal_record.order_id
        base = "normal"
        if label in {"AS", "AR", "ADVANCE SALE", "ADVANCE REFUND", "ADVANCE"}:
            base = "advance"
        elif label in {"NS", "NF", "NORMAL SALE", "NORMAL REFUND"}:
            base = "normal"
        elif "ADVANCE" in label:
            base = "advance"
        is_refund = bool(order and order.amount_total < 0)
        suffix = "refund" if is_refund else "sale"
        key = f"{base}_{suffix}"
        if key not in {"normal_sale", "normal_refund", "advance_sale", "advance_refund"}:
            key = "normal_refund" if is_refund else "normal_sale"
        return key

    @api.model
    def get_tax_label(self, product_id):
        product = self.env["product.product"].browse(product_id)
        if not product:
            return False
        taxes = product.taxes_id
        rate = round(sum(t.amount for t in taxes), 2) if taxes else 0.0
        mapping = {
            12.5: "G",
            9.0: "A",
            0.0: "B",
        }
        return mapping.get(rate, "UNKNOWN")
    



class PosOrder(models.Model):
    _inherit = "pos.order"

    def _process_order(self, order, existing_order):
        payload = order.pop("taxcore_payload")
        invoiceNum = order.pop("invoice_number")
        sdcInvoice = order.pop("sdc_invoice", False)
        invLabel = order.pop("invoice_label")
        order_id = super()._process_order(order, existing_order)
        order_rec = self.browse(order_id)
        
        if payload:
            self.env["pos.order.fiscal.record"].create({
                "order_id": order_id,
                "payload": payload,
                "invoice_number": invoiceNum,
                "sdc_invoice": sdcInvoice,
                "invoice_label": invLabel,
            })
            order_rec.taxcore_journal = payload 
        if invLabel:
            order_rec.write({"invoice_label": invLabel})
        return order_id
