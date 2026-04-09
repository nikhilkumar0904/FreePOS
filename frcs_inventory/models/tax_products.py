from odoo import api, fields, models


class TaxProducts(models.Model):
    _name = "tax.products"
    _description = "Taxable and Non-Taxable Products View"
    _auto = False

    name = fields.Char(string="Product Name")
    categ_id = fields.Many2one('product.category', string="Category")
    tax_status = fields.Selection([
        ('taxable', 'Taxable'),
        ('non_taxable', 'Non-Taxable')
    ], string="Tax Type")

    @api.model
    def init(self):
        cr = self.env.cr
        # Detect the M2M relation table name used by this Odoo version
        cr.execute("SELECT to_regclass('public.product_template_account_tax_rel')")
        rel_new = cr.fetchone()[0]
        cr.execute("SELECT to_regclass('public.product_taxes_rel')")
        rel_old = cr.fetchone()[0]

        if rel_new:
            rel_table = 'product_template_account_tax_rel'
            rel_col = 'product_tmpl_id'
        elif rel_old:
            rel_table = 'product_taxes_rel'
            rel_col = 'prod_id'
        else:
            # Fallback: assume no relation table present (unlikely), everything non-taxable
            rel_table = None
            rel_col = None

        cr.execute("DROP VIEW IF EXISTS tax_products CASCADE")

        if rel_table:
            create_sql = f"""
                CREATE VIEW tax_products AS (
                    SELECT
                        pt.id AS id,
                        pt.name AS name,
                        pt.categ_id AS categ_id,
                        CASE WHEN EXISTS (
                            SELECT 1 FROM {rel_table} r WHERE r.{rel_col} = pt.id
                        ) THEN 'taxable' ELSE 'non_taxable' END AS tax_status
                    FROM product_template pt
                )
            """
        else:
            create_sql = """
                CREATE VIEW tax_products AS (
                    SELECT
                        pt.id AS id,
                        pt.name AS name,
                        pt.categ_id AS categ_id,
                        'non_taxable'::varchar AS tax_status
                    FROM product_template pt
                )
            """

        cr.execute(create_sql)

