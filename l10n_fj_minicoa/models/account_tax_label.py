# frcs_label field removed — use the standard Odoo invoice_label field instead.
# invoice_label is already on account.tax and is what TaxCore sync reads/writes.
# Having a separate frcs_label field creates confusion and is unused by any sync logic.
