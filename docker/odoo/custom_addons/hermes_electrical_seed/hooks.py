from odoo import api, SUPERUSER_ID

ALLOWED_SKUS = {
    "CTRL-PANEL-A1",
    "LED-STRIP-24V-1M",
    "BRACKET-STEEL-001",
    "PCB-CTRL-REV21",
    "ENCLOSURE-IP65-300",
    "PSU-24VDC-5A",
    "CABLE-ASSY-2M",
    "SCREW-M4X12-DIN912",
    "RELAY-SAFETY-24V",
    "ESTOP-BTN-RED",
    "TFT-DISPLAY-7IN",
}


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    ProductTemplate = env["product.template"]

    hermes_products = ProductTemplate.search([
        ("default_code", "in", list(ALLOWED_SKUS))
    ])
    if hermes_products:
        hermes_products.write({"active": True})

    archive_domain = [
        ("default_code", "!=", False),
        ("type", "=", "product"),
        ("default_code", "not in", list(ALLOWED_SKUS))
    ]
    to_archive = ProductTemplate.search(archive_domain)
    if to_archive:
        to_archive.write({"active": False})
