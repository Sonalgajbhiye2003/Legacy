# Vendor notes

- Module: `web_chatter_position_cr`
- Publisher: CandidRoot Solutions Pvt. Ltd.
- Odoo Apps source: https://apps.odoo.com/apps/modules/17.0/web_chatter_position_cr
- License: LGPL-3
- Odoo version: 17.0

The Odoo Apps download requires an authenticated Odoo account. The source was
obtained from the public `bird17_test` mirror of the same technical module and
the mirror's mechanical `bird` namespace substitutions were restored to
`odoo`.

Local adjustments:

- use a valid Odoo manifest version (`17.0.1.0.0`);
- default new users to the Bottom chatter position;
- fall back to Bottom while an older Odoo worker has not yet loaded the new
  user preference field.
