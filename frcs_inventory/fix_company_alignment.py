from odoo import api, SUPERUSER_ID


def align_tax_companies(env, target_company=None):
    """
    Align tax repartition lines to the same company as their parent tax.

    Scope: Fiji VAT taxes (name like 'VAT %' and optional country = FJ) to avoid touching unrelated data.
    If target_company is given, further restrict to that company; otherwise, uses env.company.
    """
    if target_company is None:
        target_company = env.company

    if not target_company:
        return

    cr = env.cr
    fj = env.ref('base.fj', raise_if_not_found=False)
    fj_id = fj.id if fj else None

    # Align lines: set l.company_id = t.company_id for mismatched Fiji VAT taxes
    params = []
    where = []
    if fj_id:
        where.append("t.country_id = %s")
        params.append(fj_id)
    where.append("t.name ILIKE 'VAT %'")
    where.append("(l.company_id IS DISTINCT FROM t.company_id)")
    where.append("(t.company_id = %s)")
    params.append(target_company.id)

    where_sql = " AND ".join(where)
    cr.execute(f"""
        UPDATE account_tax_repartition_line AS l
           SET company_id = t.company_id
          FROM account_tax AS t
         WHERE l.tax_id = t.id
           AND {where_sql}
    """, params)
