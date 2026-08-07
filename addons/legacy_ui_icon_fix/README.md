# Legacy UI Icon Fix

Restores the standard Odoo 17 **Apps** and **Settings** icons on the home
menu. The installed `to_base` branding hook otherwise replaces both special
base icons with the same generic fallback image.

The module refreshes the cached menu images on installation and preserves the
correct icon calculation during subsequent menu updates.
