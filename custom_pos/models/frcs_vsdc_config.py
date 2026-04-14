from odoo import models, fields, api
from odoo.exceptions import UserError
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
import base64
from odoo.tools.safe_eval import safe_eval

import logging
_logger = logging.getLogger(__name__)


class FrcsVsdcConfig(models.Model):
    _name = "frcs.vsdc.config"
    _description = "FRCS V-SDC Configuration"
    _rec_name = "company_id"

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    vsdc_url = fields.Char(
        string="V-SDC API URL",
        required=True,
        help="Base URL, e.g. https://vsdc.sandbox.vms.frcs.org.fj"
    )
    pac = fields.Char(
        string="PAC",
        required=True,
    )
    pfx_file = fields.Binary(
        string="PFX Certificate",
        help="Client certificate issued by FRCS (PFX/P12).",
    )
    pfx_filename = fields.Char(string="PFX Filename")

    pfx_password = fields.Char(
        string="PFX Password",
        help="Password provided with the PFX.",
    )

    # Extracted PEM versions (never exposed in UI)
    cert_pem = fields.Binary(string="Certificate (PEM)", readonly=True)
    key_pem = fields.Binary(string="Private Key (PEM)", readonly=True)

    cert_status = fields.Char(
        string="Certificate Status",
        compute="_compute_cert_status",
        store=False,
    )

    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "company_unique",
            "unique(company_id)",
            "Only one FRCS V-SDC configuration is allowed per company.",
        )
    ]

    @api.depends("cert_pem", "key_pem", "pfx_file")
    def _compute_cert_status(self):
        for rec in self:
            if rec.cert_pem and rec.key_pem:
                rec.cert_status = "✅ Certificate extracted and ready"
            elif rec.pfx_file:
                rec.cert_status = "⚠️ PFX uploaded but not yet converted — click 'Convert Certificate'"
            else:
                rec.cert_status = "❌ No certificate uploaded"

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.pfx_file and record.pfx_password:
            record._convert_pfx_to_pem()
        return record

    def write(self, vals):
        res = super().write(vals)
        if "pfx_file" in vals or "pfx_password" in vals:
            for rec in self:
                if rec.pfx_file and rec.pfx_password:
                    rec._convert_pfx_to_pem()
        return res

    def action_convert_pfx(self):
        """Manual button to force PFX -> PEM conversion."""
        for rec in self:
            if not rec.pfx_file:
                raise UserError("Please upload a PFX certificate file first.")
            if not rec.pfx_password:
                raise UserError("Please enter the PFX password first.")
            rec._convert_pfx_to_pem()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": "Certificate converted successfully. You can now use TaxCore.",
                "type": "success",
                "sticky": False,
            },
        }

    def _convert_pfx_to_pem(self):
        for rec in self:
            if not rec.pfx_file or not rec.pfx_password:
                _logger.warning("FrcsVsdcConfig: skipping PFX conversion - missing file or password")
                continue

            try:
                pfx_bytes = base64.b64decode(rec.pfx_file)
                password_bytes = rec.pfx_password.encode("utf-8")

                key, cert, extra_certs = pkcs12.load_key_and_certificates(
                    pfx_bytes,
                    password_bytes,
                )

                if cert is None:
                    raise UserError("No certificate found inside the PFX file.")
                if key is None:
                    raise UserError("No private key found inside the PFX file.")

                cert_pem_bytes = cert.public_bytes(Encoding.PEM)
                key_pem_bytes = key.private_bytes(
                    encoding=Encoding.PEM,
                    format=PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=NoEncryption(),
                )

                rec.cert_pem = base64.b64encode(cert_pem_bytes)
                rec.key_pem = base64.b64encode(key_pem_bytes)

                _logger.info("FrcsVsdcConfig: PFX successfully converted to PEM for company %s", rec.company_id.name)

            except UserError:
                raise
            except Exception as e:
                _logger.exception("FrcsVsdcConfig: PFX conversion failed")
                raise UserError(
                    f"Failed to parse PFX certificate: {e}\n\n"
                    "Please check:\n"
                    "- The file is a valid PFX/P12 certificate\n"
                    "- The password is correct\n"
                    "- The certificate was issued by FRCS"
                )

    def action_sync_tax_rates(self):
        """Fetch tax rates from TaxCore and sync into Odoo taxes."""
        result = self.env['taxcore.client'].sync_tax_rates_from_taxcore()

        if result.get('success'):
            synced = result.get('synced', [])
            labels = result.get('labels', {})
            label_summary = ', '.join(
                f"{l}={info['rate']}% ({info['name']})"
                for l, info in labels.items()
            )
            msg = (
                f"Tax rates synced from TaxCore.\n"
                f"Available: {label_summary}\n"
                f"Updated: {', '.join(synced) if synced else 'none (already up to date)'}"
            )
            msg_type = "success"
        else:
            msg = f"Failed to sync tax rates: {result.get('error', 'Unknown error')}"
            msg_type = "danger"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "TaxCore Tax Sync",
                "message": msg,
                "type": msg_type,
                "sticky": True,
            },
        }

    @api.model
    def get_pos_number(self, company_id=None):
        """Return the POS number in FRCS required format: accreditation/version
        FRCS-assigned constants — do not change without FRCS approval.
        """
        accreditation_number = "182"
        system_version = "1.0.0"
        return f"{accreditation_number}/{system_version}"

    @api.model
    def action_open_company_settings(self):
        action = self.env.ref("custom_pos.action_frcs_vsdc_config").read()[0]
        config = self.search(
            [("company_id", "=", self.env.company.id)],
            limit=1,
        )
        if config:
            action["res_id"] = config.id
            action["views"] = [
                (self.env.ref("custom_pos.view_frcs_vsdc_config_form").id, "form")
            ]
            action["view_mode"] = "form"
        else:
            action["views"] = [
                (self.env.ref("custom_pos.view_frcs_vsdc_config_list").id, "list"),
                (self.env.ref("custom_pos.view_frcs_vsdc_config_form").id, "form"),
            ]
            action["view_mode"] = "list,form"

        base_ctx = action.get("context") or "{}"
        safe_locals = {
            "uid": self.env.user,
            "user": self.env.user,
        }
        ctx = safe_eval(base_ctx, safe_locals)
        ctx["default_company_id"] = self.env.company.id
        action["context"] = ctx
        action["domain"] = [("company_id", "=", self.env.company.id)]
        return action
