import base64
import logging
import uuid
from pathlib import Path

import requests

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import config as odoo_config

_logger = logging.getLogger(__name__)

class TaxCoreClient(models.AbstractModel):
    _name = "taxcore.client"
    _description = "Helper to talk to TaxCore V3"

    def _get_cert_dir(self):
        param_dir = odoo_config.get("taxcore_cert_dir")
        if param_dir:
            base_dir = Path(param_dir)
        else:
            data_dir = odoo_config.get("data_dir") or odoo_config.fallback("data_dir")
            base_dir = Path(data_dir or ".") / "taxcore_certs"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @api.model
    def send_invoice_v3(self, invoice):
        _logger.info("=== TaxCore send_invoice_v3 called ===")

        company = self.env.company
        _logger.info("Company: %s (id=%s)", company.name, company.id)

        config = self.env["frcs.vsdc.config"].search(
            [("company_id", "=", company.id), ("active", "=", True)],
            limit=1,
        )
        if not config:
            _logger.error("TaxCore: No FRCS V-SDC config found for company %s", company.id)
            raise UserError("FRCS V-SDC configuration not found for this company.")

        _logger.info("Config found: url=%s, pac=%s", config.vsdc_url, config.pac)
        _logger.info("cert_pem present: %s, key_pem present: %s",
                     bool(config.cert_pem), bool(config.key_pem))

        if not config.cert_pem or not config.key_pem:
            _logger.error("TaxCore: Certificate not configured for company %s", company.id)
            raise UserError("Certificate not configured correctly for this company.")

        try:
            cert_bytes = base64.b64decode(config.cert_pem)
            key_bytes = base64.b64decode(config.key_pem)
            _logger.info("TaxCore: cert decoded OK (%d bytes), key decoded OK (%d bytes)",
                         len(cert_bytes), len(key_bytes))
        except Exception as e:
            _logger.error("TaxCore: Failed to decode cert/key: %s", e)
            raise UserError(f"Failed to decode certificate: {e}")

        pac = config.pac
        url = config.vsdc_url.rstrip("/") + "/api/v3/invoices"
        _logger.info("TaxCore: posting to URL: %s", url)

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "en-US",
            "PAC": pac,
        }

        invoice = dict(invoice or {})
        invoice.setdefault("PAC", pac)
        _logger.info("TaxCore: invoice payload keys: %s", list(invoice.keys()))
        _logger.info("TaxCore: InvoiceNumber=%s, invoiceType=%s, transactionType=%s",
                     invoice.get("InvoiceNumber"),
                     invoice.get("invoiceType"),
                     invoice.get("transactionType"))
        _logger.info("TaxCore: payment=%s", invoice.get("payment"))
        _logger.info("TaxCore: items count=%s", len(invoice.get("Items", [])))

        base_dir = self._get_cert_dir()
        cert_path = base_dir / f"{company.id}_{uuid.uuid4().hex}_cert.pem"
        key_path = base_dir / f"{company.id}_{uuid.uuid4().hex}_key.pem"
        _logger.info("TaxCore: writing cert to %s", cert_path)

        try:
            cert_path.write_bytes(cert_bytes)
            key_path.write_bytes(key_bytes)
            _logger.info("TaxCore: cert files written OK, making request...")

            response = requests.post(
                url,
                json=invoice,
                headers=headers,
                timeout=20,
                cert=(str(cert_path), str(key_path)),
            )
            _logger.info("TaxCore: response status=%s", response.status_code)
            _logger.info("TaxCore: response body=%s", response.text[:500])

        except requests.exceptions.SSLError as e:
            _logger.error("TaxCore: SSL error: %s", e)
            raise UserError(f"TaxCore SSL certificate error: {e}")
        except requests.exceptions.ConnectionError as e:
            _logger.error("TaxCore: Connection error: %s", e)
            raise UserError(f"TaxCore connection failed - check the V-SDC URL: {e}")
        except requests.exceptions.Timeout:
            _logger.error("TaxCore: Request timed out after 20s")
            raise UserError("TaxCore request timed out. The server did not respond in time.")
        except Exception as e:
            _logger.exception("TaxCore: Unexpected error during request")
            raise UserError(f"TaxCore unexpected error: {e}")
        finally:
            for path in (cert_path, key_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError as unlink_error:
                    _logger.warning("Failed to remove temp cert file %s: %s", path, unlink_error)

        if not response.ok:
            body = response.text
            _logger.error("TaxCore call failed (%s): %s", response.status_code, body)
            raise UserError(_(f"TaxCore API error ({response.status_code}): {body}"))

        _logger.info("TaxCore: success!")
        return response.json()
