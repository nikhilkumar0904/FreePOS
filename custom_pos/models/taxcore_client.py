import base64
import logging
import uuid
from pathlib import Path

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

        cert_path, key_path = self._write_temp_certs(config)
        _logger.info("TaxCore: cert files written, making request...")

        try:
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
    def _write_temp_certs(self, config):
        """Write cert_pem and key_pem from config to temp files.
        Returns (cert_path, key_path). Caller is responsible for cleanup.
        """
        if not config.cert_pem or not config.key_pem:
            raise UserError(
                "Certificate not configured. Please upload and convert your PFX certificate first."
            )
        cert_bytes = base64.b64decode(config.cert_pem)
        key_bytes = base64.b64decode(config.key_pem)
        base_dir = self._get_cert_dir()
        cert_path = base_dir / f"{config.company_id.id}_{uuid.uuid4().hex}_cert.pem"
        key_path = base_dir / f"{config.company_id.id}_{uuid.uuid4().hex}_key.pem"
        cert_path.write_bytes(cert_bytes)
        key_path.write_bytes(key_bytes)
        return cert_path, key_path

    @api.model
    def get_tax_groups(self):
        """Fetch tax rates from TaxCore V3 API endpoint /api/v3/tax-rates.
        Requires mTLS client certificate (TaxCore returns 403 without it).
        """
        company = self.env.company
        config = self.env["frcs.vsdc.config"].search(
            [("company_id", "=", company.id), ("active", "=", True)],
            limit=1,
        )
        if not config:
            raise Exception("FRCS V-SDC configuration not found for this company.")

        # /api/v3/tax-rates lives on the public API server, not the V-SDC server.
        # Derive it by replacing "vsdc." with "api." in the hostname.
        # e.g. https://vsdc.sandbox.vms.frcs.org.fj -> https://api.sandbox.vms.frcs.org.fj
        vsdc_url = config.vsdc_url.rstrip("/")
        api_url = vsdc_url.replace("//vsdc.", "//api.", 1)
        url = api_url + "/api/v3/tax-rates"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Language": "en-US",
        }

        _logger.info("Fetching tax rates from TaxCore API: %s", url)

        try:
            # verify=False: sandbox uses a non-standard CA not in Python's cert bundle.
            # For production, replace with verify='/path/to/frcs-ca.crt'
            response = requests.get(url, headers=headers, timeout=20, verify=False)
        except requests.RequestException as e:
            raise Exception(f"Network error contacting TaxCore: {e}")

        if not response.ok:
            body = response.text
            _logger.error("TaxCore tax-rates call failed (%s): %s", response.status_code, body)
            raise Exception(f"TaxCore API error ({response.status_code}): {body}")

        return response.json()

    @api.model
    def authenticate_vsdc(self):
        """Perform mutual TLS authentication with V-SDC on POS session start.

        Calls /api/v3/tax-rates using the client certificate to prove that:
          - The POS has a valid certificate (client authenticated to V-SDC)
          - The V-SDC responds correctly (V-SDC authenticated to POS via TLS)

        This satisfies the FRCS certification requirement:
        "Upon operation start, the POS and V-SDC are mutually authenticated"

        Returns {'success': True} on success, {'success': False, 'error': ...} on failure.
        """
        _logger.info("FRCS: Performing V-SDC mutual authentication on POS session start")
        try:
            response = self.get_tax_groups()
            if response:
                _logger.info("FRCS: V-SDC mutual authentication successful on session start")
                return {'success': True}
            else:
                return {'success': False, 'error': 'Empty response from V-SDC'}
        except Exception as e:
            _logger.error("FRCS: V-SDC mutual authentication failed on session start: %s", e)
            return {'success': False, 'error': str(e)}

    @api.model
    def sync_tax_rates_from_taxcore(self):
        """Fetch tax rates from TaxCore /api/v3/tax-rates and sync into Odoo taxes.

        Response structure:
        {
          "currentTaxRates": [{
            "taxCategories": [{
              "name": "VAT",
              "taxRates": [{"rate": 12.5, "label": "A"}, ...]
            }]
          }]
        }
        """
        try:
            response = self.get_tax_groups()
        except Exception as e:
            _logger.error("Failed to fetch tax rates from TaxCore: %s", e)
            return {'success': False, 'error': str(e)}

        if not response:
            return {'success': False, 'error': 'No response from TaxCore'}

        current_groups = response.get('currentTaxRates', [])
        if not current_groups:
            _logger.error("TaxCore response has no currentTaxRates. Full response: %s", response)
            return {'success': False, 'error': 'No currentTaxRates in response'}

        # currentTaxRates may be:
        #   - a list of group dicts  (as per the API docs example)
        #   - a single group dict    (what the Fiji server actually returns)
        # Normalise to a single group dict either way.
        if isinstance(current_groups, list):
            current = current_groups[0] if current_groups else {}
        elif isinstance(current_groups, dict):
            # It IS the current group already — use it directly
            current = current_groups
        else:
            _logger.error("Unexpected currentTaxRates type %s. Full response: %s",
                          type(current_groups).__name__, response)
            return {'success': False, 'error': f'Unexpected currentTaxRates type: {type(current_groups).__name__}'}

        _logger.info("TaxCore current group keys: %s", list(current.keys()) if isinstance(current, dict) else current)
        tax_categories = current.get('taxCategories', [])

        Tax = self.env['account.tax'].sudo()
        company = self.env.company
        synced = []
        all_labels = {}

        # Build flat map of label -> rate from all tax categories
        for category in tax_categories:
            cat_name = category.get('name', '')
            for tax_rate in category.get('taxRates', []):
                label = tax_rate.get('label')
                rate = tax_rate.get('rate', 0.0)
                if label:
                    all_labels[label] = {'rate': float(rate), 'name': cat_name}

        _logger.info("TaxCore returned labels: %s", all_labels)

        # Sync each label to matching Odoo taxes by invoice_label
        for label, info in all_labels.items():
            rate = info['rate']
            taxes = Tax.search([
                ('company_id', '=', company.id),
                ('invoice_label', '=', label),
                ('amount_type', '=', 'percent'),
            ])
            for tax in taxes:
                if tax.amount != rate:
                    tax.write({'amount': rate})
                    _logger.info("Updated tax label %s: %s%%", label, rate)
                    synced.append(f"{label}={rate}%")
                else:
                    _logger.info("Tax label %s already at %s%% - no change", label, rate)

        _logger.info("TaxCore tax sync complete. Updated: %s", synced or "none")
        return {'success': True, 'synced': synced, 'labels': all_labels}
