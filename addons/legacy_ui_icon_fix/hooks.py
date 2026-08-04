import base64

from odoo import tools
from odoo.addons.base.models.ir_ui_menu import IrUiMenu


STANDARD_MENU_ICONS = {
    "base,static/description/modules.png",
    "base,static/description/settings.png",
}


def _read_standard_icon(web_icon):
    module, path = web_icon.split(",", 1)
    with tools.file_open(
        f"{module}/{path}",
        "rb",
        filter_ext=(".png",),
    ) as icon_file:
        return base64.encodebytes(icon_file.read())


def post_load():
    """Keep the two special base icons out of third-party branding fallback."""
    original_compute = IrUiMenu._compute_web_icon_data

    def _compute_web_icon_data(self, web_icon):
        if web_icon in STANDARD_MENU_ICONS:
            return _read_standard_icon(web_icon)
        return original_compute(self, web_icon)

    IrUiMenu._compute_web_icon_data = _compute_web_icon_data


def post_init_hook(env):
    """Replace stale cached menu binaries when the fix is installed."""
    for xmlid in ("base.menu_management", "base.menu_administration"):
        menu = env.ref(xmlid)
        menu.sudo().write({"web_icon_data": _read_standard_icon(menu.web_icon)})
