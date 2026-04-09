from odoo import models, fields, _, api
import logging

_logger = logging.getLogger(__name__)


class TaxBulkWizard(models.TransientModel):
    _name = 'tax.bulk.wizard'
    _description = 'Bulk Apply or Remove Taxes'

    tax_id = fields.Many2one(
        'account.tax',
        string="Tax to Apply",
        required=True,
        domain="[('type_tax_use','=','sale')]",
        help="Customer tax to apply on selected products.",
    )
    action_type = fields.Selection([
        ('replace', 'Replace Existing Taxes'),
        ('add', 'Add Tax'),
        ('remove', 'Remove Tax'),
    ], string="Action", required=True, default='replace')

    @api.model
    def default_get(self, fields_list):
        """Allow server actions to preselect a tax via context key
        default_tax_selection in: vat_0, vat_9, vat_125, vat_15, remove.
        """
        res = super().default_get(fields_list)
        sel = self.env.context.get('default_tax_selection')
        if not sel:
            return res

        if sel == 'remove':
            if 'action_type' in self._fields:
                res['action_type'] = 'remove'
            return res

        amount_map = {
            'vat_0': 0.0,
            'vat_9': 9.0,
            'vat_125': 12.5,
            'vat_15': 15.0,
        }
        rate = amount_map.get(sel)
        if rate is None:
            return res

        Tax = self.env['account.tax'].with_company(self.env.company)
        domain = [
            ('type_tax_use', '=', 'sale'),
            ('amount_type', '=', 'percent'),
            ('amount', '=', rate),
            ('active', '=', True),
        ]
        preferred = Tax.search(domain + [('tax_group_id.name', '=', 'FRCS VAT')], limit=1) or Tax.search(domain, limit=1)
        if preferred and 'tax_id' in self._fields:
            res['tax_id'] = preferred.id
        if 'action_type' in self._fields:
            res.setdefault('action_type', 'replace')
        return res

    def action_confirm(self):
        self.ensure_one()
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return {'type': 'ir.actions.act_window_close'}

        ProductTmpl = self.env['product.template']
        products = ProductTmpl.browse(active_ids)
        cr = self.env.cr
        applied = 0

        tax = self.tax_id
        tax_id = tax.id
        action = self.action_type
        _logger.info("Bulk tax action: %s on %d products (tax_id=%s)", action, len(products), tax_id)

        # --- Safer: ORM-only path, sync template + variants, and custom display field ---
        applied = 0
        for product in products:
            current_taxes = product.taxes_id

            if action == 'add':
                new_taxes = (current_taxes | tax)
            elif action == 'replace':
                new_taxes = tax
            elif action == 'remove':
                new_taxes = current_taxes - tax
            else:
                continue

            vals_to_write = {
                'taxes_id': [(6, 0, new_taxes.ids)],
            }
            # Sync custom FRCS display field on template if it exists
            if 'x_sale_tax_id' in product._fields:
                if action == 'remove':
                    vals_to_write['x_sale_tax_id'] = False
                else:
                    vals_to_write['x_sale_tax_id'] = tax.id

            product.write(vals_to_write)

            # Variants mirror template
            for variant in product.product_variant_ids:
                variant_vals = {
                    'taxes_id': [(6, 0, new_taxes.ids)],
                }
                if 'x_sale_tax_id' in self.env['product.product']._fields:
                    if action == 'remove':
                        variant_vals['x_sale_tax_id'] = False
                    else:
                        variant_vals['x_sale_tax_id'] = tax.id
                variant.write(variant_vals)

            applied += 1

        # Commit + refresh + recompute for UI
        self.env.cr.commit()
        try:
            self.env['product.template'].invalidate_cache(['taxes_id'])
            self.env['product.product'].invalidate_cache(['taxes_id'])
            # Final safeguard: ensure variants mirror the template state
            for product in products:
                tmpl_tax_ids = product.taxes_id.ids
                if tmpl_tax_ids:
                    product.product_variant_ids.write({'taxes_id': [(6, 0, tmpl_tax_ids)]})
                else:
                    product.product_variant_ids.write({'taxes_id': [(5, 0, 0)]})
            fields_to_recompute = [f for f in ('x_sale_tax_rate', 'x_tax_amount') if f in self.env['product.template']._fields]
            if fields_to_recompute:
                products.recompute(fields_to_recompute)
                self.env.cr.commit()
        except Exception:
            pass

        return {
            'type': 'ir.actions.act_window_close',
            'effect': {
                'fadeout': 'slow',
                'message': _('✅ Taxes updated on %s products successfully!') % applied,
                'type': 'rainbow_man',
            },
        }

        # Detect relation table and column (varies by Odoo version)
        rel_table = None
        prod_col = None
        try:
            cr.execute("SELECT to_regclass('public.product_template_account_tax_rel')")
            if cr.fetchone() and cr.fetchone() is None:
                pass
        except Exception:
            pass
        try:
            cr.execute("SELECT to_regclass('public.product_template_account_tax_rel')")
            row = cr.fetchone()
            if row and row[0]:
                rel_table = 'product_template_account_tax_rel'
                prod_col = 'product_tmpl_id'
            else:
                cr.execute("SELECT to_regclass('public.product_taxes_rel')")
                row2 = cr.fetchone()
                if row2 and row2[0]:
                    rel_table = 'product_taxes_rel'
                    prod_col = 'prod_id'
        except Exception as e:
            _logger.debug("Relation detection failed: %s", e)

        clear_all_on_remove = (action == 'remove' and not self.tax_id)

        if not rel_table:
            # Fallback to ORM writes
            for product in products:
                try:
                    # Ensure company match for the selected tax
                    tax_to_use = self.tax_id
                    if tax_to_use.company_id and product.company_id and tax_to_use.company_id.id != product.company_id.id:
                        Tax = self.env['account.tax'].with_company(product.company_id)
                        mapped = Tax.search([
                            ('type_tax_use', '=', 'sale'),
                            ('amount_type', '=', 'percent'),
                            ('amount', '=', float(self.tax_id.amount or 0.0))
                        ], limit=1)
                        if mapped:
                            tax_to_use = mapped

                    if action == 'replace':
                        _logger.warning("BulkTax ORM replace | tmpl=%s id=%s tax=%s(%s)", product.display_name, product.id, tax_to_use.display_name if tax_to_use else None, tax_to_use.id if tax_to_use else None)
                        product.taxes_id = [(5, 0, 0)]
                        product.write({'taxes_id': [(6, 0, [tax_to_use.id])]})
                    elif action == 'add':
                        _logger.warning("BulkTax ORM add | tmpl=%s id=%s tax=%s(%s)", product.display_name, product.id, tax_to_use.display_name if tax_to_use else None, tax_to_use.id if tax_to_use else None)
                        if tax_to_use.id not in product.taxes_id.ids:
                            product.write({'taxes_id': [(4, tax_to_use.id)]})
                    elif action == 'remove':
                        _logger.warning("BulkTax ORM remove | tmpl=%s id=%s tax=%s(%s) clear_all=%s", product.display_name, product.id, (tax_to_use.display_name if tax_to_use else None), (tax_to_use.id if tax_to_use else None), clear_all_on_remove)
                        if clear_all_on_remove:
                            product.write({'taxes_id': [(5, 0, 0)]})
                        else:
                            if tax_to_use.id in product.taxes_id.ids:
                                product.write({'taxes_id': [(3, tax_to_use.id)]})
                    applied += 1
                except Exception as e:
                    _logger.warning("Failed to update product %s via ORM: %s", product.display_name, e)
        else:
            # Direct SQL on M2M rel table for templates
            ids_tuple = tuple(products.ids)
            try:
                if action == 'replace':
                    cr.execute(f"DELETE FROM {rel_table} WHERE {prod_col} IN %s", (ids_tuple,))
                    for pid in products.ids:
                        cr.execute(f"INSERT INTO {rel_table} ({prod_col}, tax_id) VALUES (%s, %s)", (pid, tax_id))
                    _logger.warning("BulkTax SQL replace | rel=%s col=%s count=%s tax_id=%s", rel_table, prod_col, len(products), tax_id)
                elif action == 'add':
                    for pid in products.ids:
                        cr.execute(
                            f"""
                            INSERT INTO {rel_table} ({prod_col}, tax_id)
                            SELECT %s, %s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM {rel_table}
                                WHERE {prod_col} = %s AND tax_id = %s
                            )
                            """,
                            (pid, tax_id, pid, tax_id),
                        )
                    _logger.warning("BulkTax SQL add | rel=%s col=%s count=%s tax_id=%s", rel_table, prod_col, len(products), tax_id)
                elif action == 'remove':
                    if clear_all_on_remove:
                        cr.execute(f"DELETE FROM {rel_table} WHERE {prod_col} IN %s", (ids_tuple,))
                        _logger.warning("BulkTax SQL remove-all | rel=%s col=%s count=%s", rel_table, prod_col, len(products))
                    else:
                        cr.execute(f"DELETE FROM {rel_table} WHERE {prod_col} IN %s AND tax_id = %s", (ids_tuple, tax_id))
                        _logger.warning("BulkTax SQL remove-one | rel=%s col=%s count=%s tax_id=%s", rel_table, prod_col, len(products), tax_id)
                applied = len(products)
            except Exception as e:
                _logger.warning("SQL bulk update failed, falling back to ORM: %s", e)
                # Fallback to ORM per product
                for product in products:
                    try:
                        if action == 'replace':
                            product.taxes_id = [(5, 0, 0)]
                            product.write({'taxes_id': [(6, 0, [tax_id])]})
                        elif action == 'add':
                            if tax_id not in product.taxes_id.ids:
                                product.write({'taxes_id': [(4, tax_id)]})
                        elif action == 'remove':
                            if tax_id in product.taxes_id.ids:
                                product.write({'taxes_id': [(3, tax_id)]})
                    except Exception as e2:
                        _logger.warning("Fallback ORM failed for %s: %s", product.display_name, e2)
                applied = len(products)

        # Commit and invalidate caches so UI refreshes
        cr.commit()
        try:
            self.env['product.template'].invalidate_cache(['taxes_id'])
            self.env['product.product'].invalidate_cache(['taxes_id'])
            # Ensure variants mirror the final template taxes
            for product in products:
                tmpl_tax_ids = product.taxes_id.ids
                if tmpl_tax_ids:
                    product.product_variant_ids.write({'taxes_id': [(6, 0, tmpl_tax_ids)]})
                else:
                    product.product_variant_ids.write({'taxes_id': [(5, 0, 0)]})
        except Exception:
            pass

        # Force recompute of display helpers if present (stored computes)
        try:
            fields_to_recompute = [f for f in ('x_sale_tax_rate', 'x_tax_amount')
                                   if f in self.env['product.template']._fields]
            if fields_to_recompute:
                products.recompute(fields_to_recompute)
                cr.commit()
                self.env.invalidate_all()
                _logger.info("Recomputed fields after bulk tax update: %s", fields_to_recompute)
        except Exception:
            # Best-effort: never block the wizard on recompute
            pass

        return {
            'type': 'ir.actions.act_window_close',
            'effect': {
                'fadeout': 'slow',
                'message': _('✅ Taxes updated on %s products successfully!') % applied,
                'type': 'rainbow_man',
            },
        }

