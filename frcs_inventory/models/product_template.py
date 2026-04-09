from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re

# GTIN: allow exactly 8, 12, 13 or 14 digits
_GTIN_RE = re.compile(r"^(?:\d{8}|\d{12}|\d{13}|\d{14})$")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    _sql_constraints = [
        ('frcs_gtin_uniq', 'unique(frcs_gtin)', 'GTIN must be unique among products.'),
        ('x_product_code_uniq', 'unique(x_product_code)', 'Product Code must be unique among products.'),
    ]

    # New fields for custom layout/logic
    x_product_code = fields.Char(string="Product Code", copy=False, index=True,
                                 help="Unique product code.")
    x_product_description = fields.Text(string="Product Description",
                                        help="If empty, receipts will use the product name.")
    x_expiry_date = fields.Date(string="Product Expiry",
                                help="Simple product-level expiry. For lots/serial expiry, use lot-based settings.")

    # Supplier information (simple fields)
    x_supplier_code = fields.Char(string="Supplier Code", size=64)
    x_supplier_name = fields.Char(string="Supplier Name", size=128)
    x_stock_in_date = fields.Date(string="Stock-in Date")
    x_purchase_tax_id = fields.Many2one(
        "account.tax", string="Purchase Tax",
        domain="[('type_tax_use','=','purchase'),('amount_type','=','percent'),('amount','in',[0.0,12.5]), ('tax_group_id.name', '=', 'FRCS VAT')]",
        help="Allowed: 0% or 12.5% purchase tax (FRCS VAT group).")
    # Mirror of native On Hand (qty_available) for the list view column
    x_purchase_qty = fields.Integer(
        string="On Hand",
        compute="_compute_on_hand_qty",
        store=False,
    )

    # Editable On Hand on the form: mirrors qty_available and lets user adjust
    x_onhand_manual = fields.Integer(
        string="On Hand",
        help="Edit to set On Hand quantity (integer) for this product at the main Stock location.",
        compute="_compute_onhand_manual",
        inverse="_inverse_onhand_manual",
        store=False,
    )

    # Sales information
    x_sale_tax_id = fields.Many2one(
        "account.tax", string="FRCS Sales Tax",
        domain="[('type_tax_use','=','sale'),('amount_type','=','percent'),('amount','in',[0.0,12.5]), ('tax_group_id.name', '=', 'FRCS VAT')]",
        help="Allowed: FRCS VAT 0% or 12.5% (sales).")
    x_default_discount_amount = fields.Monetary(string="Default Discount",
                                                currency_field="currency_id",
                                                help="Flat discount amount applied by default on POS lines.")

    # Computed tax display helpers
    x_sale_tax_rate = fields.Float(string="FRCS Tax %", compute="_compute_tax_display", store=True)
    x_tax_amount = fields.Monetary(string="Tax (FJ$)", compute="_compute_tax_display", currency_field="currency_id", store=True)
    x_price_incl_tax = fields.Monetary(string="Total Price (FJ$)", compute="_compute_tax_display", currency_field="currency_id", store=True)
    # New explicit alias field for clarity in views
    x_total_price = fields.Monetary(string="Total Price (FJ$)", compute="_compute_tax_display", currency_field="currency_id", store=True)

    # POS: tax-included total for product tile/line display
    total_price = fields.Float(
        string="Total Price (Tax Included)",
        compute="_compute_total_price_pos",
        store=False,
        help="Tax-included unit price computed for POS display.",
    )

    # New tax selector fields per request
    frcs_tax_id = fields.Many2one(
        "account.tax",
        string="FRCS Tax",
        domain="[('type_tax_use','=','sale'), ('name','ilike','FRCS VAT'), ('amount_type','=','percent'), ('amount','in',[0.0,12.5])]",
        help="Select FRCS VAT (0% or 12.5%) applicable to this product (sales).",
    )
    purchase_tax = fields.Many2one(
        "account.tax",
        string="Purchase Tax",
        domain="[('type_tax_use','=','purchase')]",
        help="Select FRCS VAT for purchases (0% or 12.5%).",
    )

    # Keep existing GTIN but alias it for UI/search consistency
    frcs_gtin = fields.Char(
        string="GTIN",
        help="Global Trade Item Number (8/12/13/14 digits).",
        copy=False,
        index=True,
        tracking=True,
    )
    x_gtin = fields.Char(related="frcs_gtin", string="GTIN", store=True, readonly=False, copy=False)

    # Flags for search filters
    x_is_expired = fields.Boolean(string="Expired", compute="_compute_expiry_flags", store=True)
    x_is_expiring_soon = fields.Boolean(string="Expiring Soon", compute="_compute_expiry_flags", store=True)

    # Tax grouping helper for UI: Taxable vs Non-Taxable (0% or no tax)
    tax_category = fields.Selection(
        selection=[
            ('taxable', 'Taxable'),
            ('non_taxable', 'Non-Taxable'),
        ],
        string="Tax Category",
        compute="_compute_tax_category",
        store=True,
    )

    @api.depends(
        'taxes_id', 'taxes_id.amount', 'taxes_id.amount_type',
        'taxes_id.children_tax_ids', 'taxes_id.children_tax_ids.amount'
    )
    def _compute_tax_category(self):
        for product in self:
            taxable = False
            for tax in product.taxes_id:
                amt = tax.amount or 0.0
                if getattr(tax, 'amount_type', '') == 'group':
                    for child in getattr(tax, 'children_tax_ids', []):
                        if (child.amount or 0.0) > 0:
                            amt = child.amount
                            break
                if amt > 0:
                    taxable = True
                    break
            product.tax_category = 'taxable' if taxable else 'non_taxable'

    # Legacy keyword-based classification kept for backward-compatibility
    tax_status = fields.Selection(
        selection=[
            ('taxable', 'Taxable Products'),
            ('non_taxable', 'Non-Taxable Products'),
        ],
        string='Tax Category',
        compute='_compute_tax_status',
        store=True,
    )

    frcs_tax_label = fields.Selection(
        selection=[
            ("A", "A (15%)"),
            ("E", "E (9%)"),
            ("F", "F (0%)"),
            ("P", "P (0.25%)"),
        ],
        string="FRCS Tax Label",
        help="Legacy FRCS label.",
        tracking=True,
    )

    # UI-only helper to display fixed product type label
    x_product_type_label = fields.Char(string="Product Type", compute="_compute_product_type_label")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'type' in fields_list and not res.get('type'):
            # Force default to Goods
            res['type'] = 'consu'
        return res

    @api.model
    def create(self, vals):
        # Ensure created products default to Goods
        vals.setdefault('type', 'consu')
        # Block past expiry dates on create
        if vals.get('x_expiry_date'):
            from datetime import date as _date
            try:
                new_dt = fields.Date.to_date(vals['x_expiry_date'])
            except Exception:
                new_dt = vals['x_expiry_date']
            if new_dt and new_dt < _date.today():
                raise ValidationError(_("Expiry date cannot be in the past."))
        return super().create(vals)

    def write(self, vals):
        # Allow callers (e.g., recompute mirrors / bulk ops) to bypass tax sync
        if self.env.context.get('skip_tax_sync'):
            return super().write(vals)
        # Disallow switching away from Goods via UI or API
        if 'type' in vals and vals.get('type') not in (False, 'consu'):
            raise ValidationError(_("Only 'Goods' product type is allowed."))
        # Block past expiry dates on write
        if 'x_expiry_date' in vals:
            from datetime import date as _date
            try:
                new_dt = fields.Date.to_date(vals['x_expiry_date']) if vals['x_expiry_date'] else False
            except Exception:
                new_dt = vals['x_expiry_date']
            if new_dt and new_dt < _date.today():
                raise ValidationError(_("Expiry date cannot be in the past."))
        # Sync sales taxes (product.taxes_id) with our FRCS selection when relevant
        tax_to_apply = None
        if 'x_sale_tax_id' in vals and vals['x_sale_tax_id']:
            tax_to_apply = self.env['account.tax'].browse(vals['x_sale_tax_id'])

        # If label is set without explicit x_sale_tax_id, try inferring
        if not tax_to_apply and 'frcs_tax_label' in vals and vals['frcs_tax_label']:
            label = vals['frcs_tax_label']
            amount_map = {'A': 15.0, 'E': 9.0, 'F': 0.0, 'P': 0.25}
            rate = amount_map.get(label)
            if rate is not None:
                tax_to_apply = self.env['account.tax'].search([
                    ('type_tax_use', '=', 'sale'),
                    ('amount_type', '=', 'percent'),
                    ('amount', 'in', [rate, 12.5 if rate == 15.0 else rate]),
                    '|', ('company_id', '=', False), ('company_id', 'in', self.env.companies.ids)
                ], limit=1)

        res = super().write(vals)

        # Avoid recursive write() and false/invalid M2M entries during bulk ops
        if (not self.env.context.get('skip_tax_sync')) and tax_to_apply and tax_to_apply.exists():
            for rec in self:
                if rec.exists():
                    rec.taxes_id = [(6, 0, [tax_to_apply.id])]

        return res

    @api.depends('qty_available')
    def _compute_on_hand_qty(self):
        for rec in self:
            # Reflect the live On Hand from stock, shown as integer
            rec.x_purchase_qty = int(round(rec.qty_available or 0.0))

    def _compute_onhand_manual(self):
        for rec in self:
            rec.x_onhand_manual = int(round(rec.qty_available or 0.0))

    def _inverse_onhand_manual(self):
        """Adjust the real stock to match x_onhand_manual using inventory mode on the company’s main Stock location."""
        StockQuant = self.env['stock.quant']
        Warehouse = self.env['stock.warehouse']
        for rec in self:
            if rec.x_onhand_manual is None:
                continue
            if not rec.product_variant_id:
                # Ensure a variant exists
                rec.flush_recordset()
            product = rec.product_variant_id
            if not product:
                continue
            # Pick the company’s primary warehouse stock location
            warehouse = Warehouse.search([('company_id', '=', rec.company_id.id or self.env.company.id)], limit=1)
            location = warehouse.lot_stock_id if warehouse else None
            if not location:
                try:
                    location = self.env.ref('stock.stock_location_stock')
                except Exception:
                    location = None
            if not location:
                raise UserError(_("No stock location found to adjust On Hand."))

            # Apply an inventory adjustment using stock.quant in inventory mode
            desired = int(rec.x_onhand_manual or 0)
            if desired < 0:
                raise UserError(_("On Hand cannot be negative."))
            # Create/edit quant in inventory mode with target quantity then apply
            StockQuant.with_context(inventory_mode=True).create({
                'product_id': product.id,
                'location_id': location.id,
                'inventory_quantity': desired,
            })._apply_inventory()

    def _compute_total_price_pos(self):
        for rec in self:
            price = rec.list_price or 0.0
            try:
                taxes = rec.taxes_id
                if taxes:
                    # Use Odoo's tax engine to compute included total
                    res = taxes.compute_all(price, currency=rec.currency_id, quantity=1.0, product=rec, partner=False)
                    total = res.get('total_included', price)
                else:
                    total = price
            except Exception:
                total = price
            rec.total_price = float(round(total, (rec.currency_id and rec.currency_id.decimal_places) or 2))

    @api.depends('name', 'categ_id')
    def _compute_tax_status(self):
        """
        Classify products as Taxable vs Non-Taxable based on FRCS zero-rated keywords.
        If no tax is set yet, auto-assign Sales tax (0% for zero-rated, else 15% if available,
        falling back to 12.5% when 15% is not present).
        """
        # Narrow, explicit FRCS zero-rated keywords to reduce false positives
        zero_rated_keywords = [
            'baby milk', 'canned fish', 'cooking oil', 'dhal', 'flour',
            'garlic', 'kerosene', 'liquid milk', 'onion', 'potato',
            'powdered milk', 'rice', 'salt', 'sanitary pad', 'soap',
            'detergent', 'sugar', 'tea', 'toilet paper', 'toothpaste'
        ]

        def _find_frcs_sales_tax(rate):
            domain = [
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
                ('amount', '=', rate),
                ('active', '=', True),
                '|', ('tax_group_id.name', 'ilike', 'FRCS'), ('name', 'ilike', 'VAT'),
            ]
            return self.env['account.tax'].search(domain, limit=1)

        for rec in self:
            name_l = (rec.name or '').lower()
            is_zero_rated = any(k in name_l for k in zero_rated_keywords)
            rec.tax_status = 'non_taxable' if is_zero_rated else 'taxable'

            # Auto-assign taxes only when not already assigned
            if not rec.taxes_id:
                tax_to_set = False
                # Try explicit FRCS XML IDs first, then fallback to search by rate
                tax_0_ref = self.env.ref('l10n_fj_minicoa.tax_frcs_vat_0_sales', raise_if_not_found=False)
                tax_15_ref = self.env.ref('l10n_fj_minicoa.tax_frcs_vat_15_sales', raise_if_not_found=False)
                if is_zero_rated:
                    tax_to_set = tax_0_ref or _find_frcs_sales_tax(0.0)
                else:
                    tax_to_set = tax_15_ref or _find_frcs_sales_tax(15.0) or _find_frcs_sales_tax(12.5)
                if tax_to_set:
                    rec.taxes_id = [(6, 0, [tax_to_set.id])]
                    # keep custom display fields in sync when present
                    if hasattr(rec, 'x_sale_tax_id'):
                        rec.x_sale_tax_id = tax_to_set

    # ------------------------------
    # Tax helpers and synchronization
    # ------------------------------
    @api.depends(
        'list_price', 'currency_id',
        'x_sale_tax_id', 'x_sale_tax_id.amount', 'x_sale_tax_id.amount_type', 'x_sale_tax_id.price_include',
        'frcs_tax_id', 'frcs_tax_id.amount', 'frcs_tax_id.amount_type', 'frcs_tax_id.price_include',
        # also react when the native customer taxes change (bulk ops)
        'taxes_id', 'taxes_id.amount', 'taxes_id.amount_type', 'taxes_id.price_include'
    )
    def _compute_tax_display(self):
        for rec in self:
            # Prefer explicit FRCS fields, then fall back to the first sale tax on the product
            tax = rec.x_sale_tax_id or rec.frcs_tax_id
            if not tax and rec.taxes_id:
                tax = rec.taxes_id.filtered(lambda t: t.type_tax_use == 'sale')[:1]
            price = rec.list_price or 0.0
            rate = 0.0
            tax_amount = 0.0
            price_incl = price
            if tax:
                if tax.amount_type == 'percent':
                    rate = (tax.amount or 0.0) / 100.0
                    if rate:
                        if tax.price_include:
                            # price already includes tax -> extract tax portion,
                            # but for display we still show Price Incl = price + tax
                            # (requested behavior)
                            try:
                                net = price / (1.0 + rate)
                            except Exception:
                                net = price
                            tax_amount = price - net
                        else:
                            tax_amount = price * rate
                else:
                    # fixed tax or other types
                    tax_amount = tax.amount or 0.0
            # Always display Price Incl Tax = Sales Price + Tax amount
            price_incl = price + tax_amount

            # Round per currency settings
            digits = rec.currency_id and rec.currency_id.decimal_places or 2
            rec.x_sale_tax_rate = (tax.amount if tax and tax.amount_type == 'percent' else 0.0)
            rec.x_tax_amount = round(tax_amount, digits)
            rec.x_price_incl_tax = round(price_incl, digits)
            rec.x_total_price = rec.x_price_incl_tax

    @api.onchange('frcs_tax_label')
    def _onchange_frcs_tax_label_sync_tax(self):
        """Keep FRCS label and selected sales tax in sync when user changes the label."""
        label_to_rate = {
            'A': 15.0,
            'E': 9.0,
            'F': 0.0,
            'P': 0.25,
        }
        for rec in self:
            rate = label_to_rate.get(rec.frcs_tax_label)
            if rate is None:
                continue
            tax = rec.env['account.tax'].search([
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
                ('amount', 'in', [rate, 12.5 if rate == 15.0 else rate]),  # accept legacy 12.5% if needed
                '|', ('company_id', '=', False), ('company_id', 'in', rec.allowed_company_ids.ids if hasattr(rec, 'allowed_company_ids') else [rec.company_id.id] )
            ], limit=1)
            if tax:
                rec.x_sale_tax_id = tax

    @api.onchange('x_sale_tax_id')
    def _onchange_x_sale_tax_id_sync_label(self):
        amount_to_label = {
            15.0: 'A',
            12.5: 'A',  # legacy mapping
            9.0: 'E',
            0.0: 'F',
            0.25: 'P',
        }
        for rec in self:
            if rec.x_sale_tax_id and rec.x_sale_tax_id.amount_type == 'percent':
                label = amount_to_label.get(round(rec.x_sale_tax_id.amount or 0.0, 2))
                if label:
                    rec.frcs_tax_label = label
                # keep product taxes in sync for accounting/POS
                rec.taxes_id = [(6, 0, [rec.x_sale_tax_id.id])]

    @api.onchange('taxes_id')
    def _onchange_taxes_id_sync_label(self):
        for rec in self:
            sale_tax = rec.taxes_id.filtered(lambda t: t.type_tax_use == 'sale')[:1]
            if sale_tax:
                label = getattr(sale_tax, 'label_on_invoice', False)
                if not label and sale_tax.amount_type == 'percent':
                    label_map = {
                        15.0: 'A',
                        12.5: 'A',
                        9.0: 'E',
                        0.0: 'F',
                        0.25: 'P',
                    }
                    label = label_map.get(round(sale_tax.amount or 0.0, 2))
                rec.frcs_tax_label = label
            else:
                rec.frcs_tax_label = False

    @api.constrains("frcs_gtin")
    def _check_frcs_gtin(self):
        for rec in self:
            if rec.frcs_gtin and not _GTIN_RE.match(rec.frcs_gtin):
                raise ValidationError(_("GTIN must be 8, 12, 13 or 14 digits (no spaces or letters)."))
            if rec.frcs_gtin:
                #Check for uniqueness across products (simple check)
                dup = self.search([("frcs_gtin", "=", rec.frcs_gtin), ("id", "!=", rec.id)], limit=1)
                if dup:
                    raise ValidationError(_("GTIN %s is already used by another product.") % rec.frcs_gtin)
    
    @api.constrains("barcode", "frcs_gtin")
    def _check_barcode_matches_gtin(self):
        """
        If barcode is present AND is purely 8–14 digits (i.e., looks like a GTIN),
        then it must match frcs_gtin to avoid mismatches during POS scanning & fiscalization.
        """
        for rec in self:
            if rec.barcode and _GTIN_RE.match(rec.barcode):
                if not rec.frcs_gtin:
                    raise ValidationError(_("Barcode looks like a GTIN, but GTIN field is empty. Please set GTIN to match the barcode."))
                if rec.barcode != rec.frcs_gtin:
                    raise ValidationError(_("Barcode (%s) looks like a GTIN and must equal GTIN (%s).") % (rec.barcode, rec.frcs_gtin))

    @api.onchange("frcs_gtin")
    def _onchange_frcs_gtin_fill_barcode(self):
        """If barcode is empty and GTIN is set/valid, use it as barcode for convenience."""
        for rec in self:
            if rec.frcs_gtin and _GTIN_RE.match(rec.frcs_gtin) and not rec.barcode:
                rec.barcode = rec.frcs_gtin

    # Dashboard data providers for the custom Inventory dashboard
    @api.model
    def get_top_selling_products(self):
        """Return top 10 fast-moving products.
        Prefer POS data if available; otherwise fall back to Sale Orders when present.
        """
        cr = self.env.cr
        rows = []
        pos_available = False
        try:
            cr.execute("SELECT to_regclass('public.pos_order_line')")
            row = cr.fetchone()
            pos_available = bool(row and row[0])
        except Exception:
            pos_available = False

        if pos_available:
            cr.execute(
                """
                SELECT pt.id AS product_tmpl_id, COALESCE(SUM(pol.qty), 0) AS qty_sold
                FROM pos_order_line pol
                JOIN pos_order po ON pol.order_id = po.id
                JOIN product_product pp ON pol.product_id = pp.id
                JOIN product_template pt ON pp.product_tmpl_id = pt.id
                WHERE po.state IN ('paid','done','invoiced')
                GROUP BY pt.id
                ORDER BY qty_sold DESC
                LIMIT 10
                """
            )
            rows = cr.dictfetchall()
        else:
            sale_available = False
            try:
                cr.execute("SELECT to_regclass('public.sale_order_line')")
                row = cr.fetchone()
                sale_available = bool(row and row[0])
            except Exception:
                sale_available = False
            if sale_available:
                cr.execute(
                    """
                    SELECT pt.id AS product_tmpl_id, COALESCE(SUM(sol.product_uom_qty), 0) AS qty_sold
                    FROM sale_order_line sol
                    JOIN sale_order so ON sol.order_id = so.id
                    JOIN product_product pp ON sol.product_id = pp.id
                    JOIN product_template pt ON pp.product_tmpl_id = pt.id
                    WHERE so.state IN ('sale','done')
                    GROUP BY pt.id
                    ORDER BY qty_sold DESC
                    LIMIT 10
                    """
                )
                rows = cr.dictfetchall()

        if not rows:
            return []

        tmpl_ids = [row.get("product_tmpl_id") for row in rows if row.get("product_tmpl_id")]
        names = {}
        if tmpl_ids:
            templates = self.browse(tmpl_ids)
            names = {rec.id: rec.display_name for rec in templates}

        result = []
        for row in rows:
            tmpl_id = row.get("product_tmpl_id")
            name = names.get(tmpl_id)
            result.append({
                "name": name or _("Unknown Product"),
                "qty_sold": float(row.get("qty_sold") or 0),
            })
        return result

    @api.model
    def get_expiring_products(self, days=30, limit=20):
        from datetime import date, timedelta
        today = date.today()
        soon = today + timedelta(days=int(days or 30))
        domain = [
            ('x_expiry_date', '>=', fields.Date.to_string(today)),
            ('x_expiry_date', '<=', fields.Date.to_string(soon)),
        ]
        products = self.search(domain, order='x_expiry_date asc', limit=limit)
        return [
            {
                'name': p.display_name,
                'product_expiry': p.x_expiry_date and fields.Date.to_string(p.x_expiry_date) or '',
            }
            for p in products
        ]


class ProductTemplateExt(models.Model):
    _inherit = "product.template"

    @api.constrains("barcode", "frcs_gtin")
    def _check_barcode_matches_gtin(self):
        # Obsolete legacy rule: allow GTIN and Barcode to differ
        return

    @api.constrains("barcode")
    def _check_barcode_unique(self):
        for rec in self:
            if rec.barcode:
                dup = self.search([('barcode', '=', rec.barcode), ('id', '!=', rec.id)], limit=1)
                if dup:
                    raise ValidationError(_("Barcode %s is already used by another product.") % rec.barcode)

    @api.depends('x_expiry_date')
    def _compute_expiry_flags(self):
        from datetime import date, timedelta
        today = date.today()
        soon = today + timedelta(days=30)
        for rec in self:
            rec.x_is_expired = bool(rec.x_expiry_date and rec.x_expiry_date < today)
            rec.x_is_expiring_soon = bool(rec.x_expiry_date and today <= rec.x_expiry_date <= soon)

    @api.onchange('x_expiry_date', 'type')
    def _onchange_x_expiry_date(self):
        if self.x_expiry_date:
            from datetime import date as _date
            if self.x_expiry_date < _date.today():
                # Prevent backdating in UI: reset to today and warn
                self.x_expiry_date = _date.today()
                return {
                    'warning': {
                        'title': _('Expiry date'),
                        'message': _('Expiry date cannot be in the past. It has been set to today.'),
                    }
                }
        return None

    def _compute_product_type_label(self):
        for rec in self:
            rec.x_product_type_label = _('Goods')

    @api.constrains('x_expiry_date')
    def _check_expiry_not_past(self):
        today = fields.Date.today()
        for rec in self:
            if rec.x_expiry_date and rec.x_expiry_date < today:
                raise ValidationError(_('Expiry date cannot be in the past.'))
