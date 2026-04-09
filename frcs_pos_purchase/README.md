# FRCS POS – Purchase Customizations

This module extends Odoo 18 Purchase to align vendor information with Fiji FRCS/VMS expectations so downstream POS fiscalization can rely on consistent inputs.

## Installation
1. Place `frcs_pos_purchase` inside your custom addons directory (e.g., `c:\odoo\custom_addons`).
2. Ensure the directory is listed in `addons_path`.
3. Update the Apps list and install **FRCS POS – Purchase Customizations**.

## Configuration & Usage
- Configure the vendor TIN requirement under *Settings → Purchase → FRCS Purchase*.
- Maintain tax label mappings via *Purchase → Configuration → FRCS → Tax Label Mapping*.
- Vendor forms (Sales & Purchases tab) now include FRCS TIN and VAT registered fields.
- Purchase Orders display vendor FRCS details and allow selecting configured FRCS tax labels per line.

## Quick Test
1. Create or update a vendor with an FRCS TIN and VAT status.
2. Define at least one Tax Label Mapping record (or rely on built-in defaults).
3. Enable *Require Vendor TIN* in settings and attempt to confirm a Purchase Order for a vendor without a TIN to verify the validation.
4. Confirm an order with a vendor TIN and ensure an FRCS tax label can be selected on order lines.
