from odoo import http
from odoo.http import request


class FiscalReportController(http.Controller):
    @http.route("/custom_pos/fiscal_report", type="json", auth="user")
    def get_fiscal_report(self, start_dt, end_dt, config_ids=None, session_ids=None):
        """Return fiscal report data for the requested period."""
        config_ids = config_ids or []
        session_ids = session_ids or []
        report_env = request.env["pos.order.fiscal.record"].sudo()
        return report_env.get_report_data(
            start_dt=start_dt,
            end_dt=end_dt,
            config_ids=config_ids,
            session_ids=session_ids,
        )
